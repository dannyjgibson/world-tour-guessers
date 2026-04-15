"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.models.tour import STAGE_TYPES

StageType = Literal["sprint", "reduced_sprint", "breakaway", "tt", "gc"]


class ORMModel(BaseModel):
    """Base class enabling ``from_attributes`` for ORM serialization."""

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)
    email: str | None = None


class UserOut(ORMModel):
    id: int
    display_name: str
    email: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Tours / Stages / Riders
# ---------------------------------------------------------------------------

class TourCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    year: int = Field(ge=1900, le=2100)
    pcs_slug: str = Field(min_length=1, max_length=128)
    start_date: date | None = None
    end_date: date | None = None


class StageOut(ORMModel):
    id: int
    stage_number: int
    name: str | None
    stage_date: date | None
    pcs_slug: str | None
    classified_type: str | None
    winner_rider_id: int | None
    yellow_jersey_rider_id: int | None
    green_jersey_rider_id: int | None
    polka_dot_jersey_rider_id: int | None
    white_jersey_rider_id: int | None


class TourOut(ORMModel):
    id: int
    name: str
    year: int
    pcs_slug: str
    start_date: date | None
    end_date: date | None
    stages: list[StageOut] = []


class RiderOut(ORMModel):
    id: int
    name: str
    pcs_slug: str | None
    nationality: str | None


class TourRiderOut(BaseModel):
    id: int
    rider: RiderOut
    team_name: str | None
    bib_number: int | None
    status: str


class StageCreate(BaseModel):
    """Manual stage creation — used when PCS is unavailable."""

    stage_number: int = Field(ge=1)
    name: str | None = None
    stage_date: date | None = None
    pcs_slug: str | None = None


class StageResultEntry(BaseModel):
    rider_id: int
    position: int = Field(ge=1)
    time_seconds: int | None = None


class StageResultsManual(BaseModel):
    """Manual result entry fallback — used when PCS scraping fails."""

    winner_rider_id: int | None = None
    yellow_jersey_rider_id: int | None = None
    green_jersey_rider_id: int | None = None
    polka_dot_jersey_rider_id: int | None = None
    white_jersey_rider_id: int | None = None
    results: list[StageResultEntry] = []


class StageResultOut(ORMModel):
    id: int
    rider_id: int
    position: int
    time_seconds: int | None


class StageClassify(BaseModel):
    stage_type: StageType


# ---------------------------------------------------------------------------
# Leagues
# ---------------------------------------------------------------------------

class ScoringConfigIn(BaseModel):
    stage_scoring: dict[str, Any] | None = None
    gc_scoring: dict[str, Any] | None = None
    running_bonus: dict[str, Any] | None = None


class ScoringConfigOut(ORMModel):
    stage_scoring: dict[str, Any]
    gc_scoring: dict[str, Any]
    running_bonus: dict[str, Any]


class LeagueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    tour_id: int
    scoring_config: ScoringConfigIn | None = None


class LeagueOut(ORMModel):
    id: int
    name: str
    tour_id: int
    commissioner_id: int
    invite_code: str
    scoring_config: ScoringConfigOut | None = None
    member_ids: list[int] = []


class PropBetCreate(BaseModel):
    question: str = Field(min_length=1, max_length=512)
    max_points: int = Field(ge=0, default=10)


class PropBetOut(ORMModel):
    id: int
    league_id: int
    question: str
    max_points: int


class PropBetAnswerOut(BaseModel):
    user_id: int
    answer: str


class PropBetWithAnswers(BaseModel):
    prop_bet: PropBetOut
    answers: list[PropBetAnswerOut]


class PropBetAward(BaseModel):
    user_id: int
    points: int


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

class StagePredictionIn(BaseModel):
    stage_id: int
    rider_id: int
    stage_type: StageType


class StagePredictionOut(ORMModel):
    id: int
    league_id: int
    user_id: int
    stage_id: int
    rider_id: int
    stage_type: str


class PreTourPredictionIn(BaseModel):
    gc_1st_rider_id: int
    gc_2nd_rider_id: int
    gc_3rd_rider_id: int
    sprint_jersey_rider_id: int
    kom_jersey_rider_id: int
    youth_jersey_rider_id: int


class PreTourPredictionOut(ORMModel):
    id: int
    league_id: int
    user_id: int
    gc_1st_rider_id: int
    gc_2nd_rider_id: int
    gc_3rd_rider_id: int
    sprint_jersey_rider_id: int
    kom_jersey_rider_id: int
    youth_jersey_rider_id: int


class PropBetAnswerIn(BaseModel):
    prop_bet_id: int
    answer: str = Field(min_length=1)


class PropBetAnswerRow(ORMModel):
    id: int
    prop_bet_id: int
    answer: str


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class ScoreOut(ORMModel):
    id: int
    user_id: int
    stage_id: int
    stage_pick_points: int
    running_bonus_points: int
    tour_final_points: int
    total_points: int
    breakdown: dict[str, Any]


class LeaderboardEntry(BaseModel):
    user_id: int
    display_name: str
    stage_pick_points: int
    running_bonus_points: int
    tour_final_points: int
    prop_bet_points: int
    total_points: int


class LeaderboardOut(BaseModel):
    league_id: int
    entries: list[LeaderboardEntry]


__all__ = [
    "LeaderboardEntry",
    "LeaderboardOut",
    "LeagueCreate",
    "LeagueOut",
    "PreTourPredictionIn",
    "PreTourPredictionOut",
    "PropBetAnswerIn",
    "PropBetAnswerOut",
    "PropBetAnswerRow",
    "PropBetAward",
    "PropBetCreate",
    "PropBetOut",
    "PropBetWithAnswers",
    "RiderOut",
    "ScoreOut",
    "ScoringConfigIn",
    "ScoringConfigOut",
    "STAGE_TYPES",
    "StageClassify",
    "StageCreate",
    "StageOut",
    "StagePredictionIn",
    "StagePredictionOut",
    "StageResultEntry",
    "StageResultOut",
    "StageResultsManual",
    "StageType",
    "TourCreate",
    "TourOut",
    "TourRiderOut",
    "UserCreate",
    "UserOut",
]
