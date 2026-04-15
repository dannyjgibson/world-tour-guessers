"""Tour, Stage, Rider, TourRider, StageResult models."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.league import League


# Stage type values set by the commissioner after a stage finishes.
STAGE_TYPES = ("sprint", "reduced_sprint", "breakaway", "tt", "gc")

# Rider statuses within a tour.
RIDER_STATUSES = ("active", "abandoned", "dsq", "finished")


class Tour(Base):
    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    pcs_slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Final GC + jersey winners, populated when ``score-tour-final`` runs.
    final_gc_1st_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    final_gc_2nd_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    final_gc_3rd_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    final_sprint_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    final_kom_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    final_youth_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )

    stages: Mapped[list[Stage]] = relationship(
        back_populates="tour",
        cascade="all, delete-orphan",
        order_by="Stage.stage_number",
    )
    tour_riders: Mapped[list[TourRider]] = relationship(
        back_populates="tour", cascade="all, delete-orphan"
    )
    leagues: Mapped[list[League]] = relationship(back_populates="tour")


class Rider(Base):
    __tablename__ = "riders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    pcs_slug: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(64), nullable=True)

    tour_appearances: Mapped[list[TourRider]] = relationship(
        back_populates="rider", cascade="all, delete-orphan"
    )


class TourRider(Base):
    """Join table: which riders started this tour and their status."""

    __tablename__ = "tour_riders"
    __table_args__ = (UniqueConstraint("tour_id", "rider_id", name="uq_tour_rider"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tour_id: Mapped[int] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    team_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bib_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    tour: Mapped[Tour] = relationship(back_populates="tour_riders")
    rider: Mapped[Rider] = relationship(back_populates="tour_appearances")


class Stage(Base):
    __tablename__ = "stages"
    __table_args__ = (
        UniqueConstraint("tour_id", "stage_number", name="uq_tour_stage_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tour_id: Mapped[int] = mapped_column(ForeignKey("tours.id", ondelete="CASCADE"), nullable=False)
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    stage_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pcs_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Commissioner's classification of what kind of race this turned out to be.
    # One of STAGE_TYPES. Null until classified.
    classified_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Winner + jersey holders after this stage. Populated when results import.
    winner_rider_id: Mapped[int | None] = mapped_column(ForeignKey("riders.id"), nullable=True)
    yellow_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    green_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    polka_dot_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )
    white_jersey_rider_id: Mapped[int | None] = mapped_column(
        ForeignKey("riders.id"), nullable=True
    )

    tour: Mapped[Tour] = relationship(back_populates="stages")
    results: Mapped[list[StageResult]] = relationship(
        back_populates="stage",
        cascade="all, delete-orphan",
        order_by="StageResult.position",
    )


class StageResult(Base):
    """One finisher row per stage. Full finishing order is preserved."""

    __tablename__ = "stage_results"
    __table_args__ = (
        UniqueConstraint("stage_id", "rider_id", name="uq_stage_result_rider"),
        UniqueConstraint("stage_id", "position", name="uq_stage_result_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"), nullable=False
    )
    rider_id: Mapped[int] = mapped_column(ForeignKey("riders.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # Time gap to the winner, seconds. Null for DNF/DSQ rows that we still log.
    time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stage: Mapped[Stage] = relationship(back_populates="results")
    rider: Mapped[Rider] = relationship()
