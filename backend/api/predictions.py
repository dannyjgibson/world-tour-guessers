"""Prediction endpoints: stage picks, pre-tour picks, prop bet answers."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.league import (
    League,
    LeagueMembership,
    PropBetDefinition,
)
from backend.models.prediction import (
    PreTourPrediction,
    PropBetAnswer,
    StagePrediction,
)
from backend.models.tour import Stage
from backend.schemas import (
    PreTourPredictionIn,
    PreTourPredictionOut,
    PropBetAnswerIn,
    PropBetAnswerRow,
    StagePredictionIn,
    StagePredictionOut,
)

router = APIRouter(prefix="/leagues/{league_id}/predictions", tags=["predictions"])


def _verify_membership(db: Session, league_id: int, user_id: int) -> League:
    league = db.get(League, league_id)
    if league is None:
        raise HTTPException(status_code=404, detail="League not found")
    membership = db.scalar(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this league",
        )
    return league


# ---------------------------------------------------------------------------
# Stage predictions
# ---------------------------------------------------------------------------

@router.post("/stage", response_model=StagePredictionOut)
def submit_stage_prediction(
    league_id: int,
    payload: StagePredictionIn,
    user_id: int,
    db: Session = Depends(get_db),
) -> StagePrediction:
    league = _verify_membership(db, league_id, user_id)
    stage = db.get(Stage, payload.stage_id)
    if stage is None or stage.tour_id != league.tour_id:
        raise HTTPException(status_code=400, detail="Stage does not belong to this league's tour")

    existing = db.scalar(
        select(StagePrediction).where(
            StagePrediction.league_id == league.id,
            StagePrediction.user_id == user_id,
            StagePrediction.stage_id == stage.id,
        )
    )
    if existing is None:
        existing = StagePrediction(
            league_id=league.id,
            user_id=user_id,
            stage_id=stage.id,
            rider_id=payload.rider_id,
            stage_type=payload.stage_type,
        )
        db.add(existing)
    else:
        existing.rider_id = payload.rider_id
        existing.stage_type = payload.stage_type
    db.commit()
    db.refresh(existing)
    return existing


@router.get("/stage/{stage_id}", response_model=StagePredictionOut | None)
def get_stage_prediction(
    league_id: int, stage_id: int, user_id: int, db: Session = Depends(get_db)
) -> StagePrediction | None:
    _verify_membership(db, league_id, user_id)
    return db.scalar(
        select(StagePrediction).where(
            StagePrediction.league_id == league_id,
            StagePrediction.user_id == user_id,
            StagePrediction.stage_id == stage_id,
        )
    )


# ---------------------------------------------------------------------------
# Pre-tour predictions
# ---------------------------------------------------------------------------

@router.post("/pre-tour", response_model=PreTourPredictionOut)
def submit_pre_tour_prediction(
    league_id: int,
    payload: PreTourPredictionIn,
    user_id: int,
    db: Session = Depends(get_db),
) -> PreTourPrediction:
    _verify_membership(db, league_id, user_id)
    existing = db.scalar(
        select(PreTourPrediction).where(
            PreTourPrediction.league_id == league_id,
            PreTourPrediction.user_id == user_id,
        )
    )
    if existing is None:
        existing = PreTourPrediction(
            league_id=league_id,
            user_id=user_id,
            gc_1st_rider_id=payload.gc_1st_rider_id,
            gc_2nd_rider_id=payload.gc_2nd_rider_id,
            gc_3rd_rider_id=payload.gc_3rd_rider_id,
            sprint_jersey_rider_id=payload.sprint_jersey_rider_id,
            kom_jersey_rider_id=payload.kom_jersey_rider_id,
            youth_jersey_rider_id=payload.youth_jersey_rider_id,
        )
        db.add(existing)
    else:
        existing.gc_1st_rider_id = payload.gc_1st_rider_id
        existing.gc_2nd_rider_id = payload.gc_2nd_rider_id
        existing.gc_3rd_rider_id = payload.gc_3rd_rider_id
        existing.sprint_jersey_rider_id = payload.sprint_jersey_rider_id
        existing.kom_jersey_rider_id = payload.kom_jersey_rider_id
        existing.youth_jersey_rider_id = payload.youth_jersey_rider_id
    db.commit()
    db.refresh(existing)
    return existing


@router.get("/pre-tour", response_model=PreTourPredictionOut | None)
def get_pre_tour_prediction(
    league_id: int, user_id: int, db: Session = Depends(get_db)
) -> PreTourPrediction | None:
    _verify_membership(db, league_id, user_id)
    return db.scalar(
        select(PreTourPrediction).where(
            PreTourPrediction.league_id == league_id,
            PreTourPrediction.user_id == user_id,
        )
    )


# ---------------------------------------------------------------------------
# Prop bet answers
# ---------------------------------------------------------------------------

@router.post("/prop-bet", response_model=PropBetAnswerRow)
def submit_prop_bet_answer(
    league_id: int,
    payload: PropBetAnswerIn,
    user_id: int,
    db: Session = Depends(get_db),
) -> PropBetAnswer:
    _verify_membership(db, league_id, user_id)
    prop = db.get(PropBetDefinition, payload.prop_bet_id)
    if prop is None or prop.league_id != league_id:
        raise HTTPException(status_code=404, detail="Prop bet not found in this league")

    existing = db.scalar(
        select(PropBetAnswer).where(
            PropBetAnswer.league_id == league_id,
            PropBetAnswer.user_id == user_id,
            PropBetAnswer.prop_bet_id == prop.id,
        )
    )
    if existing is None:
        existing = PropBetAnswer(
            league_id=league_id,
            user_id=user_id,
            prop_bet_id=prop.id,
            answer=payload.answer,
        )
        db.add(existing)
    else:
        existing.answer = payload.answer
    db.commit()
    db.refresh(existing)
    return existing


@router.get("/prop-bets", response_model=list[PropBetAnswerRow])
def list_prop_bet_answers(
    league_id: int, user_id: int, db: Session = Depends(get_db)
) -> list[PropBetAnswer]:
    _verify_membership(db, league_id, user_id)
    return list(
        db.scalars(
            select(PropBetAnswer)
            .where(
                PropBetAnswer.league_id == league_id,
                PropBetAnswer.user_id == user_id,
            )
            .order_by(PropBetAnswer.prop_bet_id)
        )
    )
