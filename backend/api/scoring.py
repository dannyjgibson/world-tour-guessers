"""Scoring API: trigger stage + tour-final calculations, read leaderboards."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from backend.models.league import League
from backend.models.prediction import PreTourPrediction, StagePrediction
from backend.models.score import PropBetScore, Score
from backend.models.tour import Stage, Tour
from backend.models.user import User
from backend.schemas import LeaderboardEntry, LeaderboardOut, ScoreOut
from backend.services import scoring_engine as engine

router = APIRouter(prefix="/leagues/{league_id}", tags=["scoring"])


def _get_league(db: Session, league_id: int) -> League:
    league = db.scalar(
        select(League)
        .options(
            selectinload(League.scoring_config),
            selectinload(League.memberships),
        )
        .where(League.id == league_id)
    )
    if league is None:
        raise HTTPException(status_code=404, detail="League not found")
    return league


def _upsert_score(
    db: Session,
    league_id: int,
    user_id: int,
    stage_id: int,
    *,
    stage_pick_points: int = 0,
    running_bonus_points: int = 0,
    tour_final_points: int = 0,
    breakdown: dict,
) -> Score:
    """Create or replace a Score row. The engine is idempotent."""
    existing = db.scalar(
        select(Score).where(
            Score.league_id == league_id,
            Score.user_id == user_id,
            Score.stage_id == stage_id,
        )
    )
    total = stage_pick_points + running_bonus_points + tour_final_points
    if existing is None:
        existing = Score(
            league_id=league_id,
            user_id=user_id,
            stage_id=stage_id,
            stage_pick_points=stage_pick_points,
            running_bonus_points=running_bonus_points,
            tour_final_points=tour_final_points,
            total_points=total,
            breakdown=breakdown,
        )
        db.add(existing)
    else:
        existing.stage_pick_points = stage_pick_points
        existing.running_bonus_points = running_bonus_points
        existing.tour_final_points = tour_final_points
        existing.total_points = total
        existing.breakdown = breakdown
    return existing


def _load_stage_prediction(
    db: Session, league_id: int, user_id: int, stage_id: int
) -> StagePrediction | None:
    return db.scalar(
        select(StagePrediction).where(
            StagePrediction.league_id == league_id,
            StagePrediction.user_id == user_id,
            StagePrediction.stage_id == stage_id,
        )
    )


def _load_pre_tour_prediction(
    db: Session, league_id: int, user_id: int
) -> PreTourPrediction | None:
    return db.scalar(
        select(PreTourPrediction).where(
            PreTourPrediction.league_id == league_id,
            PreTourPrediction.user_id == user_id,
        )
    )


# ---------------------------------------------------------------------------
# Score one stage
# ---------------------------------------------------------------------------

@router.post("/score-stage/{stage_id}", response_model=list[ScoreOut])
def score_stage(
    league_id: int, stage_id: int, db: Session = Depends(get_db)
) -> list[Score]:
    """Auto-score stage picks + running bonus for every league member.

    Requires: stage results imported and ``classified_type`` set. Re-running
    overwrites prior Score rows for this (league, stage).
    """
    league = _get_league(db, league_id)
    stage = db.get(Stage, stage_id)
    if stage is None or stage.tour_id != league.tour_id:
        raise HTTPException(status_code=404, detail="Stage not found in league's tour")
    if stage.classified_type is None:
        raise HTTPException(
            status_code=400,
            detail="Stage must be classified before scoring. Call /classify first.",
        )
    cfg = league.scoring_config
    assert cfg is not None

    outcome = engine.StageOutcome(
        winner_rider_id=stage.winner_rider_id,
        classified_type=stage.classified_type,
    )
    holders = engine.JerseyHolders(
        yellow_rider_id=stage.yellow_jersey_rider_id,
        green_rider_id=stage.green_jersey_rider_id,
        polka_dot_rider_id=stage.polka_dot_jersey_rider_id,
        white_rider_id=stage.white_jersey_rider_id,
    )

    rows: list[Score] = []
    for member in league.memberships:
        stage_pred_db = _load_stage_prediction(db, league.id, member.user_id, stage.id)
        pre_tour_db = _load_pre_tour_prediction(db, league.id, member.user_id)

        stage_pred = (
            engine.StagePrediction(
                rider_id=stage_pred_db.rider_id, stage_type=stage_pred_db.stage_type
            )
            if stage_pred_db is not None
            else None
        )
        pre_tour = (
            engine.PreTourPrediction(
                gc_1st_rider_id=pre_tour_db.gc_1st_rider_id,
                gc_2nd_rider_id=pre_tour_db.gc_2nd_rider_id,
                gc_3rd_rider_id=pre_tour_db.gc_3rd_rider_id,
                sprint_jersey_rider_id=pre_tour_db.sprint_jersey_rider_id,
                kom_jersey_rider_id=pre_tour_db.kom_jersey_rider_id,
                youth_jersey_rider_id=pre_tour_db.youth_jersey_rider_id,
            )
            if pre_tour_db is not None
            else None
        )

        computed = engine.score_stage(
            stage_prediction=stage_pred,
            pre_tour_prediction=pre_tour,
            outcome=outcome,
            holders=holders,
            stage_scoring=cfg.stage_scoring,
            running_bonus=cfg.running_bonus,
        )

        # Preserve any existing tour_final_points on this stage (tour-end scoring
        # writes to the final stage's Score row).
        existing = db.scalar(
            select(Score).where(
                Score.league_id == league.id,
                Score.user_id == member.user_id,
                Score.stage_id == stage.id,
            )
        )
        tour_final = existing.tour_final_points if existing else 0
        existing_breakdown = existing.breakdown if existing else {}
        tour_final_breakdown = (existing_breakdown or {}).get("tour_final") or {}
        merged_breakdown = dict(computed["breakdown"])
        if tour_final_breakdown:
            merged_breakdown["tour_final"] = tour_final_breakdown

        row = _upsert_score(
            db,
            league_id=league.id,
            user_id=member.user_id,
            stage_id=stage.id,
            stage_pick_points=computed["stage_pick_points"],
            running_bonus_points=computed["running_bonus_points"],
            tour_final_points=tour_final,
            breakdown=merged_breakdown,
        )
        rows.append(row)

    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


# ---------------------------------------------------------------------------
# Score tour final
# ---------------------------------------------------------------------------

@router.post("/score-tour-final", response_model=list[ScoreOut])
def score_tour_final(
    league_id: int, db: Session = Depends(get_db)
) -> list[Score]:
    """Score every player's pre-tour picks against the tour's final standings.

    Writes the resulting points to a Score row tied to the tour's final stage.
    The commissioner must have set the tour's ``final_*_rider_id`` columns
    (via ``/tours/{id}/final-standings`` or the PCS final-standings import).
    """
    league = _get_league(db, league_id)
    cfg = league.scoring_config
    assert cfg is not None

    tour: Tour = db.get(Tour, league.tour_id)  # type: ignore[assignment]
    final_stage = max(tour.stages, key=lambda s: s.stage_number, default=None)
    if final_stage is None:
        raise HTTPException(
            status_code=400, detail="Tour has no stages; cannot score tour final."
        )
    if tour.final_gc_1st_rider_id is None:
        raise HTTPException(
            status_code=400,
            detail="Final GC standings not set. POST /tours/{id}/final-standings first.",
        )

    standings = engine.TourFinalStandings(
        gc_1st_rider_id=tour.final_gc_1st_rider_id,
        gc_2nd_rider_id=tour.final_gc_2nd_rider_id,
        gc_3rd_rider_id=tour.final_gc_3rd_rider_id,
        sprint_jersey_rider_id=tour.final_sprint_jersey_rider_id,
        kom_jersey_rider_id=tour.final_kom_jersey_rider_id,
        youth_jersey_rider_id=tour.final_youth_jersey_rider_id,
    )

    rows: list[Score] = []
    for member in league.memberships:
        pre_tour_db = _load_pre_tour_prediction(db, league.id, member.user_id)
        pre_tour = (
            engine.PreTourPrediction(
                gc_1st_rider_id=pre_tour_db.gc_1st_rider_id,
                gc_2nd_rider_id=pre_tour_db.gc_2nd_rider_id,
                gc_3rd_rider_id=pre_tour_db.gc_3rd_rider_id,
                sprint_jersey_rider_id=pre_tour_db.sprint_jersey_rider_id,
                kom_jersey_rider_id=pre_tour_db.kom_jersey_rider_id,
                youth_jersey_rider_id=pre_tour_db.youth_jersey_rider_id,
            )
            if pre_tour_db is not None
            else None
        )
        computed = engine.score_tour_final(pre_tour, standings, cfg.gc_scoring)

        existing = db.scalar(
            select(Score).where(
                Score.league_id == league.id,
                Score.user_id == member.user_id,
                Score.stage_id == final_stage.id,
            )
        )
        base_breakdown = existing.breakdown if existing else {}
        merged_breakdown = dict(base_breakdown or {})
        merged_breakdown["tour_final"] = computed["breakdown"]

        row = _upsert_score(
            db,
            league_id=league.id,
            user_id=member.user_id,
            stage_id=final_stage.id,
            stage_pick_points=existing.stage_pick_points if existing else 0,
            running_bonus_points=existing.running_bonus_points if existing else 0,
            tour_final_points=computed["points"],
            breakdown=merged_breakdown,
        )
        rows.append(row)

    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


# ---------------------------------------------------------------------------
# Read-only: leaderboard + score breakdowns
# ---------------------------------------------------------------------------

@router.get("/leaderboard", response_model=LeaderboardOut)
def leaderboard(league_id: int, db: Session = Depends(get_db)) -> LeaderboardOut:
    league = _get_league(db, league_id)
    member_user_ids = [m.user_id for m in league.memberships]

    score_totals: dict[int, tuple[int, int, int]] = {}
    for row in db.execute(
        select(
            Score.user_id,
            func.coalesce(func.sum(Score.stage_pick_points), 0),
            func.coalesce(func.sum(Score.running_bonus_points), 0),
            func.coalesce(func.sum(Score.tour_final_points), 0),
        )
        .where(Score.league_id == league.id)
        .group_by(Score.user_id)
    ).all():
        user_id, stage_pick, running_bonus, tour_final = row
        score_totals[user_id] = (int(stage_pick), int(running_bonus), int(tour_final))

    prop_totals: dict[int, int] = {}
    for row in db.execute(
        select(
            PropBetScore.user_id,
            func.coalesce(func.sum(PropBetScore.points_awarded), 0),
        )
        .where(PropBetScore.league_id == league.id)
        .group_by(PropBetScore.user_id)
    ).all():
        prop_totals[row[0]] = int(row[1] or 0)

    users = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(member_user_ids))).all()
    }

    entries: list[LeaderboardEntry] = []
    for user_id in member_user_ids:
        user = users.get(user_id)
        if user is None:
            continue
        stage_pick, running_bonus, tour_final = score_totals.get(user_id, (0, 0, 0))
        prop = prop_totals.get(user_id, 0)
        entries.append(
            LeaderboardEntry(
                user_id=user_id,
                display_name=user.display_name,
                stage_pick_points=stage_pick,
                running_bonus_points=running_bonus,
                tour_final_points=tour_final,
                prop_bet_points=prop,
                total_points=stage_pick + running_bonus + tour_final + prop,
            )
        )

    entries.sort(key=lambda e: (-e.total_points, e.display_name.lower()))
    return LeaderboardOut(league_id=league.id, entries=entries)


@router.get("/scores/{stage_id}", response_model=list[ScoreOut])
def stage_scores(
    league_id: int, stage_id: int, db: Session = Depends(get_db)
) -> list[Score]:
    _get_league(db, league_id)
    return list(
        db.scalars(
            select(Score)
            .where(Score.league_id == league_id, Score.stage_id == stage_id)
            .order_by(Score.total_points.desc())
        )
    )


@router.get("/scores/{stage_id}/{user_id}", response_model=ScoreOut)
def user_stage_score(
    league_id: int, stage_id: int, user_id: int, db: Session = Depends(get_db)
) -> Score:
    score = db.scalar(
        select(Score).where(
            Score.league_id == league_id,
            Score.stage_id == stage_id,
            Score.user_id == user_id,
        )
    )
    if score is None:
        raise HTTPException(status_code=404, detail="No score recorded for this user/stage")
    return score


# ---------------------------------------------------------------------------
# Commissioner setting tour-final standings (manual fallback)
# ---------------------------------------------------------------------------

from pydantic import BaseModel  # noqa: E402


class FinalStandingsManual(BaseModel):
    gc_1st_rider_id: int
    gc_2nd_rider_id: int | None = None
    gc_3rd_rider_id: int | None = None
    sprint_jersey_rider_id: int | None = None
    kom_jersey_rider_id: int | None = None
    youth_jersey_rider_id: int | None = None


# Separate router mounted under /tours so the path reads naturally.
tour_final_router = APIRouter(prefix="/tours", tags=["tours"])


@tour_final_router.post("/{tour_id}/final-standings")
def set_final_standings(
    tour_id: int,
    payload: FinalStandingsManual,
    db: Session = Depends(get_db),
) -> dict:
    """Set the final GC podium + jersey winners on a tour."""
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise HTTPException(status_code=404, detail="Tour not found")
    tour.final_gc_1st_rider_id = payload.gc_1st_rider_id
    tour.final_gc_2nd_rider_id = payload.gc_2nd_rider_id
    tour.final_gc_3rd_rider_id = payload.gc_3rd_rider_id
    tour.final_sprint_jersey_rider_id = payload.sprint_jersey_rider_id
    tour.final_kom_jersey_rider_id = payload.kom_jersey_rider_id
    tour.final_youth_jersey_rider_id = payload.youth_jersey_rider_id
    db.commit()
    return {"tour_id": tour.id, "status": "ok"}
