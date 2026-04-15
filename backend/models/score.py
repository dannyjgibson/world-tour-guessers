"""Score (auto-calculated) and PropBetScore (commissioner-awarded)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.league import League, PropBetDefinition
    from backend.models.tour import Stage
    from backend.models.user import User


class Score(Base):
    """Auto-calculated score for one user for one stage of one league.

    Stage-level components: stage pick points + running bonus points.
    Tour-final components (GC podium + jersey predictions) are stored on the
    Score row tied to the tour's final stage.

    The ``breakdown`` JSON captures every atomic contribution so the UI can
    explain "why did I get these points?" without the commissioner mediating.
    """

    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("league_id", "user_id", "stage_id", name="uq_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"), nullable=False)

    stage_pick_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    running_bonus_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tour_final_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    league: Mapped[League] = relationship(back_populates="scores")
    user: Mapped[User] = relationship(back_populates="scores")
    stage: Mapped[Stage] = relationship()


class PropBetScore(Base):
    """Commissioner-awarded points for a prop bet answer."""

    __tablename__ = "prop_bet_scores"
    __table_args__ = (
        UniqueConstraint(
            "league_id", "user_id", "prop_bet_id", name="uq_prop_bet_score"
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
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    league: Mapped[League] = relationship(back_populates="prop_bet_scores")
    user: Mapped[User] = relationship(back_populates="prop_bet_scores")
    prop_bet: Mapped[PropBetDefinition] = relationship(back_populates="awarded_scores")
