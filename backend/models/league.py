"""League, LeagueMembership, ScoringConfig, PropBetDefinition."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.prediction import (
        PreTourPrediction,
        PropBetAnswer,
        StagePrediction,
    )
    from backend.models.score import PropBetScore, Score
    from backend.models.tour import Tour
    from backend.models.user import User


# Reasonable defaults that mirror the example config in plan.md.
DEFAULT_STAGE_SCORING: dict[str, int] = {
    "stage_winner": 25,
    "stage_type": 10,
}
DEFAULT_GC_SCORING: dict[str, int] = {
    "gc_exact_1st": 50,
    "gc_exact_2nd": 35,
    "gc_exact_3rd": 25,
    "gc_on_podium": 10,
    "sprint_jersey": 30,
    "kom_jersey": 30,
    "youth_jersey": 20,
}
DEFAULT_RUNNING_BONUS: dict[str, int] = {
    "yellow_jersey_per_stage": 3,
    "green_jersey_per_stage": 2,
    "polka_dot_jersey_per_stage": 2,
    "white_jersey_per_stage": 1,
}


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tour_id: Mapped[int] = mapped_column(ForeignKey("tours.id"), nullable=False)
    commissioner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # URL-safe random token used to join the league.
    invite_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    tour: Mapped[Tour] = relationship(back_populates="leagues")
    commissioner: Mapped[User] = relationship(back_populates="commissioned_leagues")
    memberships: Mapped[list[LeagueMembership]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    scoring_config: Mapped[ScoringConfig] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
        uselist=False,
    )
    prop_bets: Mapped[list[PropBetDefinition]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    stage_predictions: Mapped[list[StagePrediction]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    pre_tour_predictions: Mapped[list[PreTourPrediction]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    prop_bet_answers: Mapped[list[PropBetAnswer]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    scores: Mapped[list[Score]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )
    prop_bet_scores: Mapped[list[PropBetScore]] = relationship(
        back_populates="league", cascade="all, delete-orphan"
    )


class LeagueMembership(Base):
    __tablename__ = "league_memberships"
    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_league_membership"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    league: Mapped[League] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class ScoringConfig(Base):
    """Per-league scoring rules as JSON. Keys interpreted by the scoring engine."""

    __tablename__ = "scoring_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    stage_scoring: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    gc_scoring: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    running_bonus: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    league: Mapped[League] = relationship(back_populates="scoring_config")


class PropBetDefinition(Base):
    __tablename__ = "prop_bet_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(String(512), nullable=False)
    max_points: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    league: Mapped[League] = relationship(back_populates="prop_bets")
    answers: Mapped[list[PropBetAnswer]] = relationship(
        back_populates="prop_bet", cascade="all, delete-orphan"
    )
    awarded_scores: Mapped[list[PropBetScore]] = relationship(
        back_populates="prop_bet", cascade="all, delete-orphan"
    )
