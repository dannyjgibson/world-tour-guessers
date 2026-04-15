"""procyclingstats wrapper.

Thin isolation layer over the ``procyclingstats`` library. Every public
function returns plain dicts / lists of dicts — never ORM objects — so the
API layer owns all persistence concerns. If PCS breaks or changes its HTML,
fixes stay here and the domain logic is unaffected.

The wrapper is intentionally defensive: missing fields return ``None``
instead of raising, since PCS's scraping heuristics occasionally produce
partial data.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time_to_seconds(raw: Any) -> int | None:
    """Parse PCS time strings (``0:12:34`` or ``+1:23``) into seconds.

    Returns ``None`` for DNF/DNS/DSQ or unparseable values. The winner row
    typically has the absolute time; other rows have a gap like ``+0:42``.
    """
    if raw is None:
        return None
    text = str(raw).strip().lstrip("+")
    if not text or text.upper() in {"DNF", "DNS", "DSQ", "OTL", "-"}:
        return None
    if not re.match(r"^\d+(:\d{1,2}){1,2}$", text):
        return None
    parts = [int(p) for p in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


# ---------------------------------------------------------------------------
# Race / stage listing
# ---------------------------------------------------------------------------

def fetch_tour_stages(tour_slug: str) -> list[dict[str, Any]]:
    """Return the stages of a tour as a list of ``{number, name, date, slug}``."""
    from procyclingstats import Race

    race = Race(tour_slug)
    stages = race.stages() or []
    result: list[dict[str, Any]] = []
    for raw in stages:
        slug = raw.get("stage_url") or raw.get("url")
        number = _safe_int(raw.get("stage_number") or raw.get("stage_nr"))
        result.append(
            {
                "stage_number": number,
                "name": raw.get("stage_name") or raw.get("distance"),
                "stage_date": _safe_date(raw.get("date")),
                "pcs_slug": slug,
            }
        )
    return result


def fetch_startlist(tour_slug: str) -> list[dict[str, Any]]:
    """Return the tour's startlist as ``{name, pcs_slug, team, bib, nationality}``."""
    from procyclingstats import RaceStartlist

    startlist_slug = tour_slug.rstrip("/") + "/startlist"
    startlist = RaceStartlist(startlist_slug)
    riders = startlist.startlist() or []

    out: list[dict[str, Any]] = []
    for raw in riders:
        out.append(
            {
                "name": raw.get("rider_name"),
                "pcs_slug": raw.get("rider_url"),
                "nationality": raw.get("nationality"),
                "team_name": raw.get("team_name"),
                "bib_number": _safe_int(raw.get("rider_number")),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Stage results
# ---------------------------------------------------------------------------

def fetch_stage_results(stage_slug: str) -> dict[str, Any]:
    """Return the stage results and current jersey holders.

    Output shape::

        {
            "finishers": [
                {"position": 1, "rider_name": ..., "rider_slug": ...,
                 "time_seconds": 12345},
                ...
            ],
            "jerseys": {
                "yellow": {"rider_name": ..., "rider_slug": ...},
                "green":  ...,
                "polka":  ...,
                "white":  ...,
            },
        }

    Any jersey entry may be ``None`` if PCS didn't report it (early-stage races,
    TT prologues, etc.).
    """
    from procyclingstats import Stage

    stage = Stage(stage_slug)
    results = stage.results() or []
    finishers: list[dict[str, Any]] = []
    for row in results:
        position = _safe_int(row.get("rank"))
        if position is None:
            # DNF / DNS / DSQ rows — skip to keep the ordered list clean.
            continue
        finishers.append(
            {
                "position": position,
                "rider_name": row.get("rider_name"),
                "rider_slug": row.get("rider_url"),
                "team_name": row.get("team_name"),
                "time_seconds": _parse_time_to_seconds(row.get("time")),
            }
        )

    jerseys = {
        "yellow": _first_leader(stage, ("gc", "general_classification")),
        "green": _first_leader(stage, ("points", "points_classification")),
        "polka": _first_leader(stage, ("kom", "kom_classification", "mountains_classification")),
        "white": _first_leader(stage, ("youth", "youth_classification", "young_rider_classification")),
    }

    return {"finishers": finishers, "jerseys": jerseys}


def _first_leader(stage: Any, method_names: tuple[str, ...]) -> dict[str, Any] | None:
    """Return the #1 rider from the first method on ``stage`` that works."""
    for name in method_names:
        method = getattr(stage, name, None)
        if method is None:
            continue
        try:
            rows = method()
        except Exception:  # pragma: no cover - PCS is best-effort
            logger.debug("PCS stage.%s failed", name, exc_info=True)
            continue
        if not rows:
            continue
        top = rows[0]
        return {
            "rider_name": top.get("rider_name"),
            "rider_slug": top.get("rider_url"),
        }
    return None


def fetch_final_standings(tour_slug: str) -> dict[str, Any]:
    """Return the final GC podium + jersey winners for a finished tour.

    Output shape::

        {
            "gc_podium": [
                {"rider_name": ..., "rider_slug": ...},  # 1st
                ...,                                    # 2nd
                ...,                                    # 3rd
            ],
            "sprint_jersey": {...} | None,
            "kom_jersey":    {...} | None,
            "youth_jersey":  {...} | None,
        }
    """
    from procyclingstats import Race

    race = Race(tour_slug)

    def _top_n(method_name: str, n: int) -> list[dict[str, Any]]:
        method = getattr(race, method_name, None)
        if method is None:
            return []
        try:
            rows = method() or []
        except Exception:  # pragma: no cover
            logger.debug("PCS race.%s failed", method_name, exc_info=True)
            return []
        return [
            {"rider_name": r.get("rider_name"), "rider_slug": r.get("rider_url")}
            for r in rows[:n]
        ]

    gc = _top_n("gc", 3)
    sprint = _top_n("points", 1)
    kom = _top_n("kom", 1)
    youth = _top_n("youth", 1)

    return {
        "gc_podium": gc,
        "sprint_jersey": sprint[0] if sprint else None,
        "kom_jersey": kom[0] if kom else None,
        "youth_jersey": youth[0] if youth else None,
    }
