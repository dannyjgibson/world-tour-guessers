"""StagePrediction, PreTourPrediction, PropBetAnswer."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.league import League, PropBetDefinition
    from backend.models.tour import Rider, Stage
    from backend.models.user import User


class StagePrediction(Base):
    """A user's pick for a single stage: winner + stage type."""

    __tablename__ = "stage_predictions"
    __table_args__ = (
        UniqueConstraint(
            "league_id", "user_id", "stage_id", name="uq_stage_prediction"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"), nullable=False)

    rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    stage_type: Mapped[str] = mapped_column(String(32), nullable=False)

    league: Mapped[League] = relationship(back_populates="stage_predictions")
    user: Mapped[User] = relationship(back_populates="stage_predictions")
    stage: Mapped[Stage] = relationship()
    rider: Mapped[Rider] = relationship()


class PreTourPrediction(Base):
    """A user's 6-pick pre-tour slate: GC podium + 3 jerseys."""

    __tablename__ = "pre_tour_predictions"
    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_pre_tour_prediction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    gc_1st_rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    gc_2nd_rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    gc_3rd_rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    sprint_jersey_rider_id: Mapped[int] = mapped_column(
        ForeignKey("riders.id"), nullable=False
    )
    kom_jersey_rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    youth_jersey_rider_id: Mapped[int] = mapped_column(
        ForeignKey("riders.id"), nullable=False
    )

    league: Mapped[League] = relationship(back_populates="pre_tour_predictions")
    user: Mapped[User] = relationship(back_populates="pre_tour_predictions")


class PropBetAnswer(Base):
    """Free-text answer a player submits for a prop bet."""

    __tablename__ = "prop_bet_answers"
    __table_args__ = (
        UniqueConstraint(
            "league_id", "user_id", "prop_bet_id", name="uq_prop_bet_answer"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    prop_bet_id: Mapped[int] = mapped_column(
        ForeignKey("prop_bet_definitions.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    league: Mapped[League] = relationship(back_populates="prop_bet_answers")
    user: Mapped[User] = relationship(back_populates="prop_bet_answers")
    prop_bet: Mapped[PropBetDefinition] = relationship(back_populates="answers")
