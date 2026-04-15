"""Tour and stage endpoints: creation, PCS imports, manual fallbacks."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from backend.models.tour import Rider, Stage, StageResult, Tour, TourRider
from backend.schemas import (
    RiderOut,
    StageClassify,
    StageCreate,
    StageOut,
    StageResultsManual,
    TourCreate,
    TourOut,
    TourRiderOut,
)
from backend.services import pcs_client

router = APIRouter(prefix="/tours", tags=["tours"])


def _get_tour(db: Session, tour_id: int) -> Tour:
    tour = db.get(Tour, tour_id)
    if tour is None:
        raise HTTPException(status_code=404, detail="Tour not found")
    return tour


def _get_stage(db: Session, tour_id: int, stage_id: int) -> Stage:
    stage = db.get(Stage, stage_id)
    if stage is None or stage.tour_id != tour_id:
        raise HTTPException(status_code=404, detail="Stage not found for this tour")
    return stage


def _upsert_rider_by_slug_or_name(
    db: Session,
    name: str | None,
    pcs_slug: str | None,
    nationality: str | None = None,
) -> Rider | None:
    """Find or create a rider, preferring PCS slug as the stable identifier."""
    if not name and not pcs_slug:
        return None

    rider: Rider | None = None
    if pcs_slug:
        rider = db.scalar(select(Rider).where(Rider.pcs_slug == pcs_slug))
    if rider is None and name:
        rider = db.scalar(select(Rider).where(Rider.name == name))

    if rider is None:
        rider = Rider(name=name or pcs_slug or "unknown", pcs_slug=pcs_slug, nationality=nationality)
        db.add(rider)
        db.flush()
    else:
        if pcs_slug and not rider.pcs_slug:
            rider.pcs_slug = pcs_slug
        if nationality and not rider.nationality:
            rider.nationality = nationality
    return rider


# ---------------------------------------------------------------------------
# Tour CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=TourOut, status_code=status.HTTP_201_CREATED)
def create_tour(payload: TourCreate, db: Session = Depends(get_db)) -> Tour:
    tour = Tour(
        name=payload.name,
        year=payload.year,
        pcs_slug=payload.pcs_slug,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(tour)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tour with pcs_slug '{payload.pcs_slug}' already exists",
        ) from None
    db.refresh(tour)
    return tour


@router.get("", response_model=list[TourOut])
def list_tours(db: Session = Depends(get_db)) -> list[Tour]:
    return list(
        db.scalars(select(Tour).options(selectinload(Tour.stages)).order_by(Tour.year.desc()))
    )


@router.get("/{tour_id}", response_model=TourOut)
def get_tour(tour_id: int, db: Session = Depends(get_db)) -> Tour:
    tour = db.scalar(
        select(Tour).options(selectinload(Tour.stages)).where(Tour.id == tour_id)
    )
    if tour is None:
        raise HTTPException(status_code=404, detail="Tour not found")
    return tour


# ---------------------------------------------------------------------------
# PCS imports
# ---------------------------------------------------------------------------

@router.post("/{tour_id}/import-stages", response_model=list[StageOut])
def import_stages(tour_id: int, db: Session = Depends(get_db)) -> list[Stage]:
    tour = _get_tour(db, tour_id)
    try:
        pcs_stages = pcs_client.fetch_tour_stages(tour.pcs_slug)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PCS fetch failed: {exc}",
        ) from exc

    existing = {s.stage_number: s for s in tour.stages}
    created_or_updated: list[Stage] = []
    for raw in pcs_stages:
        number = raw.get("stage_number")
        if number is None:
            continue
        stage = existing.get(number)
        if stage is None:
            stage = Stage(tour_id=tour.id, stage_number=number)
            db.add(stage)
        stage.name = raw.get("name") or stage.name
        stage.stage_date = raw.get("stage_date") or stage.stage_date
        stage.pcs_slug = raw.get("pcs_slug") or stage.pcs_slug
        created_or_updated.append(stage)

    db.commit()
    for s in created_or_updated:
        db.refresh(s)
    return sorted(created_or_updated, key=lambda s: s.stage_number)


@router.post("/{tour_id}/stages", response_model=StageOut, status_code=status.HTTP_201_CREATED)
def create_stage_manual(
    tour_id: int, payload: StageCreate, db: Session = Depends(get_db)
) -> Stage:
    """Manual stage creation for when PCS isn't available."""
    tour = _get_tour(db, tour_id)
    stage = Stage(
        tour_id=tour.id,
        stage_number=payload.stage_number,
        name=payload.name,
        stage_date=payload.stage_date,
        pcs_slug=payload.pcs_slug,
    )
    db.add(stage)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stage {payload.stage_number} already exists for this tour",
        ) from None
    db.refresh(stage)
    return stage


@router.post("/{tour_id}/import-riders", response_model=list[TourRiderOut])
def import_riders(tour_id: int, db: Session = Depends(get_db)) -> list[TourRider]:
    tour = _get_tour(db, tour_id)
    try:
        startlist = pcs_client.fetch_startlist(tour.pcs_slug)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PCS fetch failed: {exc}",
        ) from exc

    existing = {tr.rider_id: tr for tr in tour.tour_riders}
    created: list[TourRider] = []
    for raw in startlist:
        rider = _upsert_rider_by_slug_or_name(
            db, raw.get("name"), raw.get("pcs_slug"), raw.get("nationality")
        )
        if rider is None:
            continue
        tr = existing.get(rider.id)
        if tr is None:
            tr = TourRider(
                tour_id=tour.id,
                rider_id=rider.id,
                team_name=raw.get("team_name"),
                bib_number=raw.get("bib_number"),
                status="active",
            )
            db.add(tr)
        else:
            tr.team_name = raw.get("team_name") or tr.team_name
            tr.bib_number = raw.get("bib_number") or tr.bib_number
        created.append(tr)

    db.commit()
    for tr in created:
        db.refresh(tr)
    return created


@router.get("/{tour_id}/riders", response_model=list[TourRiderOut])
def list_riders(tour_id: int, db: Session = Depends(get_db)) -> list[TourRider]:
    tour = _get_tour(db, tour_id)
    return list(
        db.scalars(
            select(TourRider)
            .where(TourRider.tour_id == tour.id)
            .options(selectinload(TourRider.rider))
            .order_by(TourRider.bib_number.asc().nullslast())
        )
    )


@router.post(
    "/{tour_id}/riders",
    response_model=RiderOut,
    status_code=status.HTTP_201_CREATED,
)
def add_rider_manual(
    tour_id: int,
    name: str,
    team_name: str | None = None,
    bib_number: int | None = None,
    nationality: str | None = None,
    db: Session = Depends(get_db),
) -> Rider:
    """Add a single rider to a tour manually (fallback)."""
    tour = _get_tour(db, tour_id)
    rider = _upsert_rider_by_slug_or_name(db, name, None, nationality)
    assert rider is not None  # name is required, so _upsert always returns
    existing = db.scalar(
        select(TourRider).where(
            TourRider.tour_id == tour.id, TourRider.rider_id == rider.id
        )
    )
    if existing is None:
        db.add(
            TourRider(
                tour_id=tour.id,
                rider_id=rider.id,
                team_name=team_name,
                bib_number=bib_number,
                status="active",
            )
        )
    db.commit()
    db.refresh(rider)
    return rider


# ---------------------------------------------------------------------------
# Stage results
# ---------------------------------------------------------------------------

def _resolve_rider_from_pcs(
    db: Session, raw: dict | None
) -> Rider | None:
    if not raw:
        return None
    return _upsert_rider_by_slug_or_name(
        db, raw.get("rider_name"), raw.get("rider_slug")
    )


@router.post(
    "/{tour_id}/stages/{stage_id}/import-results",
    response_model=StageOut,
)
def import_stage_results(
    tour_id: int, stage_id: int, db: Session = Depends(get_db)
) -> Stage:
    stage = _get_stage(db, tour_id, stage_id)
    if not stage.pcs_slug:
        raise HTTPException(
            status_code=400,
            detail="Stage has no pcs_slug. Import stages first or set one manually.",
        )
    try:
        payload = pcs_client.fetch_stage_results(stage.pcs_slug)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PCS fetch failed: {exc}",
        ) from exc

    _replace_stage_results(db, stage, payload.get("finishers", []))
    jerseys = payload.get("jerseys") or {}
    stage.yellow_jersey_rider_id = _rider_id(_resolve_rider_from_pcs(db, jerseys.get("yellow")))
    stage.green_jersey_rider_id = _rider_id(_resolve_rider_from_pcs(db, jerseys.get("green")))
    stage.polka_dot_jersey_rider_id = _rider_id(_resolve_rider_from_pcs(db, jerseys.get("polka")))
    stage.white_jersey_rider_id = _rider_id(_resolve_rider_from_pcs(db, jerseys.get("white")))

    if stage.results:
        winner = next((r for r in stage.results if r.position == 1), None)
        if winner is not None:
            stage.winner_rider_id = winner.rider_id

    db.commit()
    db.refresh(stage)
    return stage


def _rider_id(rider: Rider | None) -> int | None:
    return rider.id if rider is not None else None


def _replace_stage_results(
    db: Session, stage: Stage, finishers: list[dict]
) -> None:
    """Idempotent replacement of stage results."""
    for existing in list(stage.results):
        db.delete(existing)
    db.flush()
    for raw in finishers:
        rider = _upsert_rider_by_slug_or_name(
            db, raw.get("rider_name"), raw.get("rider_slug")
        )
        if rider is None:
            continue
        db.add(
            StageResult(
                stage_id=stage.id,
                rider_id=rider.id,
                position=raw["position"],
                time_seconds=raw.get("time_seconds"),
            )
        )


@router.post(
    "/{tour_id}/stages/{stage_id}/results-manual",
    response_model=StageOut,
)
def set_stage_results_manual(
    tour_id: int,
    stage_id: int,
    payload: StageResultsManual,
    db: Session = Depends(get_db),
) -> Stage:
    """Commissioner fallback for when PCS scraping fails."""
    stage = _get_stage(db, tour_id, stage_id)

    for existing in list(stage.results):
        db.delete(existing)
    db.flush()
    seen: set[int] = set()
    for entry in payload.results:
        if entry.rider_id in seen:
            raise HTTPException(
                status_code=400, detail=f"Duplicate rider_id {entry.rider_id} in results"
            )
        seen.add(entry.rider_id)
        db.add(
            StageResult(
                stage_id=stage.id,
                rider_id=entry.rider_id,
                position=entry.position,
                time_seconds=entry.time_seconds,
            )
        )

    if payload.winner_rider_id is not None:
        stage.winner_rider_id = payload.winner_rider_id
    elif payload.results:
        p1 = next((r for r in payload.results if r.position == 1), None)
        if p1 is not None:
            stage.winner_rider_id = p1.rider_id

    stage.yellow_jersey_rider_id = payload.yellow_jersey_rider_id
    stage.green_jersey_rider_id = payload.green_jersey_rider_id
    stage.polka_dot_jersey_rider_id = payload.polka_dot_jersey_rider_id
    stage.white_jersey_rider_id = payload.white_jersey_rider_id

    db.commit()
    db.refresh(stage)
    return stage


@router.post(
    "/{tour_id}/stages/{stage_id}/classify",
    response_model=StageOut,
)
def classify_stage(
    tour_id: int,
    stage_id: int,
    payload: StageClassify,
    db: Session = Depends(get_db),
) -> Stage:
    """Commissioner sets the actual stage type after the stage finishes."""
    stage = _get_stage(db, tour_id, stage_id)
    stage.classified_type = payload.stage_type
    db.commit()
    db.refresh(stage)
    return stage
