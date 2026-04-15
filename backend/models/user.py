"""User model. Users are identified by display name only (no auth in v1)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.league import League, LeagueMembership
    from backend.models.prediction import (
        PreTourPrediction,
        PropBetAnswer,
        StagePrediction,
    )
    from backend.models.score import PropBetScore, Score


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    memberships: Mapped[list[LeagueMembership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    commissioned_leagues: Mapped[list[League]] = relationship(back_populates="commissioner")
    stage_predictions: Mapped[list[StagePrediction]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    pre_tour_predictions: Mapped[list[PreTourPrediction]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    prop_bet_answers: Mapped[list[PropBetAnswer]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    scores: Mapped[list[Score]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    prop_bet_scores: Mapped[list[PropBetScore]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
