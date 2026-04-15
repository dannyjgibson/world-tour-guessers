"""Pure scoring functions.

The engine takes predictions + results + config as plain dicts and returns a
score dict. It has no ORM dependency and no side effects. The API layer owns
all data loading and persistence.

Why "data, not code": every commissioner's scoring system is different.
Scoring config is JSON on ``ScoringConfig``; the engine reads keys it
recognizes and ignores the rest (with a warning).

Public functions:

- ``score_stage_picks``      — winner + stage type picks for one stage.
- ``score_running_bonus``    — 4 jersey checks for one stage.
- ``score_stage``            — convenience wrapper combining the two.
- ``score_tour_final``       — GC podium + 3 jersey predictions vs final standings.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring config key sets
# ---------------------------------------------------------------------------

STAGE_SCORING_KEYS: frozenset[str] = frozenset({"stage_winner", "stage_type"})

GC_SCORING_KEYS: frozenset[str] = frozenset({
    "gc_exact_1st",
    "gc_exact_2nd",
    "gc_exact_3rd",
    "gc_on_podium",
    "sprint_jersey",
    "kom_jersey",
    "youth_jersey",
})

RUNNING_BONUS_KEYS: frozenset[str] = frozenset({
    "yellow_jersey_per_stage",
    "green_jersey_per_stage",
    "polka_dot_jersey_per_stage",
    "white_jersey_per_stage",
})


def _warn_unknown_keys(config: dict[str, Any], known: frozenset[str], label: str) -> None:
    unknown = set(config) - known
    if unknown:
        logger.warning("Unknown %s config keys ignored: %s", label, sorted(unknown))


# ---------------------------------------------------------------------------
# Stage picks (winner + type)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StagePrediction:
    """Minimal projection of a user's stage pick."""

    rider_id: int
    stage_type: str


@dataclass(frozen=True)
class StageOutcome:
    """Actual stage results needed for scoring stage picks."""

    winner_rider_id: int | None
    classified_type: str | None


def score_stage_picks(
    prediction: StagePrediction | None,
    outcome: StageOutcome,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Score one user's stage picks.

    Returns a dict with ``points`` and ``breakdown``. Unknown config keys are
    ignored. A missing prediction scores 0.
    """
    _warn_unknown_keys(config, STAGE_SCORING_KEYS, "stage_scoring")

    if prediction is None:
        return {"points": 0, "breakdown": {"missing_prediction": True}}

    breakdown: dict[str, Any] = {
        "predicted_rider_id": prediction.rider_id,
        "predicted_stage_type": prediction.stage_type,
        "actual_winner_rider_id": outcome.winner_rider_id,
        "actual_stage_type": outcome.classified_type,
    }

    points = 0

    if (
        outcome.winner_rider_id is not None
        and prediction.rider_id == outcome.winner_rider_id
    ):
        winner_points = int(config.get("stage_winner", 0))
        points += winner_points
        breakdown["stage_winner_points"] = winner_points
    else:
        breakdown["stage_winner_points"] = 0

    if (
        outcome.classified_type is not None
        and prediction.stage_type == outcome.classified_type
    ):
        type_points = int(config.get("stage_type", 0))
        points += type_points
        breakdown["stage_type_points"] = type_points
    else:
        breakdown["stage_type_points"] = 0

    return {"points": points, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Running bonus (4 jersey checks per stage)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PreTourPrediction:
    """A user's pre-tour slate: GC podium + 3 jersey picks."""

    gc_1st_rider_id: int
    gc_2nd_rider_id: int
    gc_3rd_rider_id: int
    sprint_jersey_rider_id: int
    kom_jersey_rider_id: int
    youth_jersey_rider_id: int


@dataclass(frozen=True)
class JerseyHolders:
    """Who held each jersey after a given stage."""

    yellow_rider_id: int | None
    green_rider_id: int | None
    polka_dot_rider_id: int | None
    white_rider_id: int | None


def score_running_bonus(
    prediction: PreTourPrediction | None,
    holders: JerseyHolders,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Award running bonus points for each jersey the user's pick currently holds.

    Important: only the GC #1 pick counts for yellow. Podium picks 2 and 3 do
    not contribute to the running bonus — that's what makes the GC winner pick
    more valuable.
    """
    _warn_unknown_keys(config, RUNNING_BONUS_KEYS, "running_bonus")

    if prediction is None:
        return {"points": 0, "breakdown": {"missing_pre_tour_prediction": True}}

    breakdown: dict[str, Any] = {}
    points = 0

    checks = (
        ("yellow", prediction.gc_1st_rider_id, holders.yellow_rider_id, "yellow_jersey_per_stage"),
        ("green", prediction.sprint_jersey_rider_id, holders.green_rider_id, "green_jersey_per_stage"),
        (
            "polka_dot",
            prediction.kom_jersey_rider_id,
            holders.polka_dot_rider_id,
            "polka_dot_jersey_per_stage",
        ),
        ("white", prediction.youth_jersey_rider_id, holders.white_rider_id, "white_jersey_per_stage"),
    )
    for label, pick_id, actual_id, config_key in checks:
        match = actual_id is not None and pick_id == actual_id
        awarded = int(config.get(config_key, 0)) if match else 0
        points += awarded
        breakdown[label] = {
            "predicted_rider_id": pick_id,
            "actual_rider_id": actual_id,
            "match": match,
            "points": awarded,
        }

    return {"points": points, "breakdown": breakdown}


# ---------------------------------------------------------------------------
# Stage convenience wrapper
# ---------------------------------------------------------------------------

def score_stage(
    stage_prediction: StagePrediction | None,
    pre_tour_prediction: PreTourPrediction | None,
    outcome: StageOutcome,
    holders: JerseyHolders,
    stage_scoring: dict[str, Any],
    running_bonus: dict[str, Any],
) -> dict[str, Any]:
    """Convenience wrapper that computes stage picks + running bonus together."""
    stage_result = score_stage_picks(stage_prediction, outcome, stage_scoring)
    bonus_result = score_running_bonus(pre_tour_prediction, holders, running_bonus)

    return {
        "stage_pick_points": stage_result["points"],
        "running_bonus_points": bonus_result["points"],
        "total_points": stage_result["points"] + bonus_result["points"],
        "breakdown": {
            "stage_picks": stage_result["breakdown"],
            "running_bonus": bonus_result["breakdown"],
        },
    }


# ---------------------------------------------------------------------------
# Tour-final scoring (pre-tour picks vs final standings)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TourFinalStandings:
    """Final classification winners at tour end."""

    gc_1st_rider_id: int | None
    gc_2nd_rider_id: int | None
    gc_3rd_rider_id: int | None
    sprint_jersey_rider_id: int | None
    kom_jersey_rider_id: int | None
    youth_jersey_rider_id: int | None


def score_tour_final(
    prediction: PreTourPrediction | None,
    standings: TourFinalStandings,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Score all 6 pre-tour picks against the final standings.

    GC scoring rules (commissioner-configured):

    - Exact position: ``gc_exact_1st`` / ``gc_exact_2nd`` / ``gc_exact_3rd``
      awarded when the predicted rider finished in exactly that position.
    - On-podium bonus: ``gc_on_podium`` awarded when the pick finished top 3
      but NOT in the exact predicted slot. Each pick can earn exact OR
      on-podium, never both.

    Jerseys are match-or-nothing: ``sprint_jersey`` / ``kom_jersey`` /
    ``youth_jersey``.
    """
    _warn_unknown_keys(config, GC_SCORING_KEYS, "gc_scoring")

    if prediction is None:
        return {"points": 0, "breakdown": {"missing_pre_tour_prediction": True}}

    breakdown: dict[str, Any] = {}
    points = 0

    final_podium = {
        standings.gc_1st_rider_id,
        standings.gc_2nd_rider_id,
        standings.gc_3rd_rider_id,
    }
    final_podium.discard(None)

    gc_slots = (
        ("gc_1st", prediction.gc_1st_rider_id, standings.gc_1st_rider_id, "gc_exact_1st"),
        ("gc_2nd", prediction.gc_2nd_rider_id, standings.gc_2nd_rider_id, "gc_exact_2nd"),
        ("gc_3rd", prediction.gc_3rd_rider_id, standings.gc_3rd_rider_id, "gc_exact_3rd"),
    )
    for label, pick_id, actual_id, exact_key in gc_slots:
        awarded = 0
        kind = "miss"
        if actual_id is not None and pick_id == actual_id:
            awarded = int(config.get(exact_key, 0))
            kind = "exact"
        elif pick_id in final_podium:
            awarded = int(config.get("gc_on_podium", 0))
            kind = "on_podium"
        points += awarded
        breakdown[label] = {
            "predicted_rider_id": pick_id,
            "actual_rider_id": actual_id,
            "result": kind,
            "points": awarded,
        }

    jersey_slots = (
        (
            "sprint_jersey",
            prediction.sprint_jersey_rider_id,
            standings.sprint_jersey_rider_id,
            "sprint_jersey",
        ),
        ("kom_jersey", prediction.kom_jersey_rider_id, standings.kom_jersey_rider_id, "kom_jersey"),
        (
            "youth_jersey",
            prediction.youth_jersey_rider_id,
            standings.youth_jersey_rider_id,
            "youth_jersey",
        ),
    )
    for label, pick_id, actual_id, config_key in jersey_slots:
        match = actual_id is not None and pick_id == actual_id
        awarded = int(config.get(config_key, 0)) if match else 0
        points += awarded
        breakdown[label] = {
            "predicted_rider_id": pick_id,
            "actual_rider_id": actual_id,
            "match": match,
            "points": awarded,
        }

    return {"points": points, "breakdown": breakdown}
