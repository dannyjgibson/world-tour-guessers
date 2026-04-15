"""League management: create, join, scoring-config updates, prop bets."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.config import get_settings
from backend.database import get_db
from backend.models.league import (
    DEFAULT_GC_SCORING,
    DEFAULT_RUNNING_BONUS,
    DEFAULT_STAGE_SCORING,
    League,
    LeagueMembership,
    PropBetDefinition,
    ScoringConfig,
)
from backend.models.score import PropBetScore
from backend.models.tour import Tour
from backend.models.user import User
from backend.schemas import (
    LeagueCreate,
    LeagueOut,
    PropBetAnswerOut,
    PropBetAward,
    PropBetCreate,
    PropBetOut,
    PropBetWithAnswers,
    ScoringConfigIn,
    ScoringConfigOut,
)

router = APIRouter(prefix="/leagues", tags=["leagues"])


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(get_settings().invite_code_bytes)


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


def _require_commissioner(league: League, user_id: int) -> None:
    if league.commissioner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the commissioner can perform this action",
        )


def _league_to_out(league: League) -> LeagueOut:
    return LeagueOut(
        id=league.id,
        name=league.name,
        tour_id=league.tour_id,
        commissioner_id=league.commissioner_id,
        invite_code=league.invite_code,
        scoring_config=(
            ScoringConfigOut.model_validate(league.scoring_config)
            if league.scoring_config
            else None
        ),
        member_ids=[m.user_id for m in league.memberships],
    )


# ---------------------------------------------------------------------------
# League CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
def create_league(
    payload: LeagueCreate,
    commissioner_id: int,
    db: Session = Depends(get_db),
) -> LeagueOut:
    commissioner = db.get(User, commissioner_id)
    if commissioner is None:
        raise HTTPException(status_code=404, detail="Commissioner user not found")
    tour = db.get(Tour, payload.tour_id)
    if tour is None:
        raise HTTPException(status_code=404, detail="Tour not found")

    invite_code = _generate_invite_code()
    league = League(
        name=payload.name,
        tour_id=payload.tour_id,
        commissioner_id=commissioner_id,
        invite_code=invite_code,
    )
    db.add(league)
    db.flush()

    cfg_in = payload.scoring_config or ScoringConfigIn()
    cfg = ScoringConfig(
        league_id=league.id,
        stage_scoring=cfg_in.stage_scoring or dict(DEFAULT_STAGE_SCORING),
        gc_scoring=cfg_in.gc_scoring or dict(DEFAULT_GC_SCORING),
        running_bonus=cfg_in.running_bonus or dict(DEFAULT_RUNNING_BONUS),
    )
    db.add(cfg)

    db.add(LeagueMembership(league_id=league.id, user_id=commissioner_id))

    db.commit()
    db.refresh(league)
    return _league_to_out(_get_league(db, league.id))


@router.get("/{league_id}", response_model=LeagueOut)
def get_league(league_id: int, db: Session = Depends(get_db)) -> LeagueOut:
    return _league_to_out(_get_league(db, league_id))


@router.post("/{invite_code}/join", response_model=LeagueOut)
def join_league(
    invite_code: str, user_id: int, db: Session = Depends(get_db)
) -> LeagueOut:
    league = db.scalar(select(League).where(League.invite_code == invite_code))
    if league is None:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == user_id,
        )
    )
    if existing is None:
        db.add(LeagueMembership(league_id=league.id, user_id=user_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return _league_to_out(_get_league(db, league.id))


@router.put("/{league_id}/scoring-config", response_model=ScoringConfigOut)
def update_scoring_config(
    league_id: int,
    payload: ScoringConfigIn,
    commissioner_id: int,
    db: Session = Depends(get_db),
) -> ScoringConfig:
    league = _get_league(db, league_id)
    _require_commissioner(league, commissioner_id)
    cfg = league.scoring_config
    assert cfg is not None
    if payload.stage_scoring is not None:
        cfg.stage_scoring = payload.stage_scoring
    if payload.gc_scoring is not None:
        cfg.gc_scoring = payload.gc_scoring
    if payload.running_bonus is not None:
        cfg.running_bonus = payload.running_bonus
    db.commit()
    db.refresh(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Prop bets
# ---------------------------------------------------------------------------

@router.post(
    "/{league_id}/prop-bets",
    response_model=PropBetOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prop_bet(
    league_id: int,
    payload: PropBetCreate,
    commissioner_id: int,
    db: Session = Depends(get_db),
) -> PropBetDefinition:
    league = _get_league(db, league_id)
    _require_commissioner(league, commissioner_id)
    prop = PropBetDefinition(
        league_id=league.id, question=payload.question, max_points=payload.max_points
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("/{league_id}/prop-bets", response_model=list[PropBetWithAnswers])
def list_prop_bets(league_id: int, db: Session = Depends(get_db)) -> list[PropBetWithAnswers]:
    league = _get_league(db, league_id)
    props = db.scalars(
        select(PropBetDefinition)
        .where(PropBetDefinition.league_id == league.id)
        .options(selectinload(PropBetDefinition.answers))
        .order_by(PropBetDefinition.id)
    ).all()
    return [
        PropBetWithAnswers(
            prop_bet=PropBetOut.model_validate(prop),
            answers=[
                PropBetAnswerOut(user_id=a.user_id, answer=a.answer) for a in prop.answers
            ],
        )
        for prop in props
    ]


@router.post(
    "/{league_id}/prop-bets/{prop_bet_id}/score",
    response_model=list[PropBetAward],
)
def score_prop_bet(
    league_id: int,
    prop_bet_id: int,
    awards: list[PropBetAward],
    commissioner_id: int,
    db: Session = Depends(get_db),
) -> list[PropBetAward]:
    """Commissioner awards points per player for a prop bet.

    Awards are upserted by (league, user, prop). Max-points is enforced
    (awarded points clamped to [0, max_points]).
    """
    league = _get_league(db, league_id)
    _require_commissioner(league, commissioner_id)

    prop = db.get(PropBetDefinition, prop_bet_id)
    if prop is None or prop.league_id != league.id:
        raise HTTPException(status_code=404, detail="Prop bet not found in this league")

    member_ids = {m.user_id for m in league.memberships}

    for award in awards:
        if award.user_id not in member_ids:
            raise HTTPException(
                status_code=400,
                detail=f"User {award.user_id} is not a member of this league",
            )
        clamped = max(0, min(award.points, prop.max_points))
        existing = db.scalar(
            select(PropBetScore).where(
                PropBetScore.league_id == league.id,
                PropBetScore.user_id == award.user_id,
                PropBetScore.prop_bet_id == prop.id,
            )
        )
        if existing is None:
            db.add(
                PropBetScore(
                    league_id=league.id,
                    user_id=award.user_id,
                    prop_bet_id=prop.id,
                    points_awarded=clamped,
                )
            )
        else:
            existing.points_awarded = clamped

    db.commit()
    return awards
