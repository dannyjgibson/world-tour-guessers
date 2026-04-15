"""Unit tests for the pure scoring engine.

These test the math with known inputs/outputs — no DB, no network.
"""
from __future__ import annotations

from backend.services.scoring_engine import (
    JerseyHolders,
    PreTourPrediction,
    StageOutcome,
    StagePrediction,
    TourFinalStandings,
    score_running_bonus,
    score_stage,
    score_stage_picks,
    score_tour_final,
)

STAGE_CONFIG = {"stage_winner": 25, "stage_type": 10}

BONUS_CONFIG = {
    "yellow_jersey_per_stage": 3,
    "green_jersey_per_stage": 2,
    "polka_dot_jersey_per_stage": 2,
    "white_jersey_per_stage": 1,
}

GC_CONFIG = {
    "gc_exact_1st": 50,
    "gc_exact_2nd": 35,
    "gc_exact_3rd": 25,
    "gc_on_podium": 10,
    "sprint_jersey": 30,
    "kom_jersey": 30,
    "youth_jersey": 20,
}


# ---------------------------------------------------------------------------
# score_stage_picks
# ---------------------------------------------------------------------------

def test_stage_picks_missing_prediction_scores_zero():
    outcome = StageOutcome(winner_rider_id=7, classified_type="sprint")
    result = score_stage_picks(None, outcome, STAGE_CONFIG)
    assert result["points"] == 0
    assert result["breakdown"]["missing_prediction"] is True


def test_stage_picks_exact_winner_and_type():
    pred = StagePrediction(rider_id=7, stage_type="sprint")
    outcome = StageOutcome(winner_rider_id=7, classified_type="sprint")
    result = score_stage_picks(pred, outcome, STAGE_CONFIG)
    assert result["points"] == 35
    assert result["breakdown"]["stage_winner_points"] == 25
    assert result["breakdown"]["stage_type_points"] == 10


def test_stage_picks_type_right_winner_wrong():
    pred = StagePrediction(rider_id=7, stage_type="sprint")
    outcome = StageOutcome(winner_rider_id=9, classified_type="sprint")
    result = score_stage_picks(pred, outcome, STAGE_CONFIG)
    assert result["points"] == 10


def test_stage_picks_winner_right_type_wrong():
    pred = StagePrediction(rider_id=7, stage_type="gc")
    outcome = StageOutcome(winner_rider_id=7, classified_type="sprint")
    result = score_stage_picks(pred, outcome, STAGE_CONFIG)
    assert result["points"] == 25


def test_stage_picks_all_wrong():
    pred = StagePrediction(rider_id=7, stage_type="gc")
    outcome = StageOutcome(winner_rider_id=9, classified_type="sprint")
    result = score_stage_picks(pred, outcome, STAGE_CONFIG)
    assert result["points"] == 0


def test_stage_picks_unknown_config_keys_are_ignored():
    pred = StagePrediction(rider_id=7, stage_type="sprint")
    outcome = StageOutcome(winner_rider_id=7, classified_type="sprint")
    config = dict(STAGE_CONFIG) | {"unknown_key": 999}
    result = score_stage_picks(pred, outcome, config)
    assert result["points"] == 35


def test_stage_picks_outcome_none_winner_no_points_awarded_for_winner():
    pred = StagePrediction(rider_id=7, stage_type="sprint")
    outcome = StageOutcome(winner_rider_id=None, classified_type="sprint")
    result = score_stage_picks(pred, outcome, STAGE_CONFIG)
    # Only stage type credit awarded.
    assert result["points"] == 10


# ---------------------------------------------------------------------------
# score_running_bonus (the plan's example scenario)
# ---------------------------------------------------------------------------

POGACAR, VINGEGAARD, EVENEPOEL = 1, 2, 3
CARAPAZ, SIVAKOV = 4, 5
JAKOBSEN, POGACAR_YOUTH = 6, 7  # just distinct IDs


def test_running_bonus_plan_example_user_1():
    # GC 1st = Pogačar (holds yellow), KOM pick = Carapaz (holds polka dots).
    pred = PreTourPrediction(
        gc_1st_rider_id=POGACAR,
        gc_2nd_rider_id=VINGEGAARD,
        gc_3rd_rider_id=EVENEPOEL,
        sprint_jersey_rider_id=JAKOBSEN,
        kom_jersey_rider_id=CARAPAZ,
        youth_jersey_rider_id=POGACAR_YOUTH,
    )
    holders = JerseyHolders(
        yellow_rider_id=POGACAR,
        green_rider_id=100,  # someone else
        polka_dot_rider_id=CARAPAZ,
        white_rider_id=101,
    )
    # With bonus of {yellow:3, green:2, polka:2, white:1}, user scores 3+2=5.
    result = score_running_bonus(pred, holders, BONUS_CONFIG)
    assert result["points"] == 5
    assert result["breakdown"]["yellow"]["match"] is True
    assert result["breakdown"]["polka_dot"]["match"] is True
    assert result["breakdown"]["green"]["match"] is False
    assert result["breakdown"]["white"]["match"] is False


def test_running_bonus_plan_example_user_2():
    # GC 1st = Vingegaard (does NOT hold yellow), KOM = Sivakov (does NOT hold polka).
    pred = PreTourPrediction(
        gc_1st_rider_id=VINGEGAARD,
        gc_2nd_rider_id=POGACAR,
        gc_3rd_rider_id=EVENEPOEL,
        sprint_jersey_rider_id=JAKOBSEN,
        kom_jersey_rider_id=SIVAKOV,
        youth_jersey_rider_id=POGACAR_YOUTH,
    )
    holders = JerseyHolders(
        yellow_rider_id=POGACAR,
        green_rider_id=100,
        polka_dot_rider_id=CARAPAZ,
        white_rider_id=101,
    )
    result = score_running_bonus(pred, holders, BONUS_CONFIG)
    assert result["points"] == 0


def test_running_bonus_only_gc1_counts_for_yellow():
    """GC 2nd/3rd picks don't award yellow points even if they hold yellow."""
    pred = PreTourPrediction(
        gc_1st_rider_id=VINGEGAARD,  # not in yellow
        gc_2nd_rider_id=POGACAR,     # in yellow, but picks 2/3 don't count
        gc_3rd_rider_id=EVENEPOEL,
        sprint_jersey_rider_id=JAKOBSEN,
        kom_jersey_rider_id=CARAPAZ,
        youth_jersey_rider_id=POGACAR_YOUTH,
    )
    holders = JerseyHolders(
        yellow_rider_id=POGACAR,
        green_rider_id=None,
        polka_dot_rider_id=None,
        white_rider_id=None,
    )
    result = score_running_bonus(pred, holders, BONUS_CONFIG)
    assert result["points"] == 0


def test_running_bonus_missing_prediction_scores_zero():
    holders = JerseyHolders(
        yellow_rider_id=1, green_rider_id=2, polka_dot_rider_id=3, white_rider_id=4
    )
    assert score_running_bonus(None, holders, BONUS_CONFIG)["points"] == 0


def test_running_bonus_null_holder_does_not_match():
    pred = PreTourPrediction(
        gc_1st_rider_id=POGACAR,
        gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    holders = JerseyHolders(
        yellow_rider_id=None,  # early TT with no yellow yet, say
        green_rider_id=None,
        polka_dot_rider_id=None,
        white_rider_id=None,
    )
    assert score_running_bonus(pred, holders, BONUS_CONFIG)["points"] == 0


# ---------------------------------------------------------------------------
# score_stage (wrapper)
# ---------------------------------------------------------------------------

def test_score_stage_combines_picks_and_bonus():
    stage_pred = StagePrediction(rider_id=POGACAR, stage_type="gc")
    pre_tour = PreTourPrediction(
        gc_1st_rider_id=POGACAR, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    outcome = StageOutcome(winner_rider_id=POGACAR, classified_type="gc")
    holders = JerseyHolders(
        yellow_rider_id=POGACAR, green_rider_id=None,
        polka_dot_rider_id=None, white_rider_id=None,
    )
    result = score_stage(stage_pred, pre_tour, outcome, holders, STAGE_CONFIG, BONUS_CONFIG)
    assert result["stage_pick_points"] == 35
    assert result["running_bonus_points"] == 3
    assert result["total_points"] == 38
    assert "stage_picks" in result["breakdown"]
    assert "running_bonus" in result["breakdown"]


# ---------------------------------------------------------------------------
# score_tour_final
# ---------------------------------------------------------------------------

def _base_pre_tour():
    return PreTourPrediction(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )


def test_tour_final_all_exact():
    pred = _base_pre_tour()
    standings = TourFinalStandings(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    result = score_tour_final(pred, standings, GC_CONFIG)
    # 50 + 35 + 25 + 30 + 30 + 20 = 190
    assert result["points"] == 190
    for slot in ("gc_1st", "gc_2nd", "gc_3rd"):
        assert result["breakdown"][slot]["result"] == "exact"


def test_tour_final_on_podium_bonus_for_out_of_order_pick():
    """Predicted Pogačar 3rd but he finishes 1st. Worth gc_on_podium (10), not gc_exact_3rd."""
    pred = PreTourPrediction(
        gc_1st_rider_id=99, gc_2nd_rider_id=98, gc_3rd_rider_id=1,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    standings = TourFinalStandings(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    result = score_tour_final(pred, standings, GC_CONFIG)
    # 0 (99) + 0 (98) + 10 (on podium) + 30 + 30 + 20 = 90
    assert result["points"] == 90
    assert result["breakdown"]["gc_3rd"]["result"] == "on_podium"
    assert result["breakdown"]["gc_3rd"]["points"] == 10


def test_tour_final_miss_when_not_on_podium():
    pred = PreTourPrediction(
        gc_1st_rider_id=999, gc_2nd_rider_id=998, gc_3rd_rider_id=997,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    standings = TourFinalStandings(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    result = score_tour_final(pred, standings, GC_CONFIG)
    # All GC are misses; 3 jerseys exact = 80
    assert result["points"] == 80
    for slot in ("gc_1st", "gc_2nd", "gc_3rd"):
        assert result["breakdown"][slot]["result"] == "miss"


def test_tour_final_no_podium_bonus_when_config_omits_it():
    config = dict(GC_CONFIG)
    config.pop("gc_on_podium")
    pred = PreTourPrediction(
        gc_1st_rider_id=99, gc_2nd_rider_id=98, gc_3rd_rider_id=1,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    standings = TourFinalStandings(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    result = score_tour_final(pred, standings, config)
    # on_podium default 0, so just 30+30+20
    assert result["points"] == 80
    assert result["breakdown"]["gc_3rd"]["result"] == "on_podium"
    assert result["breakdown"]["gc_3rd"]["points"] == 0


def test_tour_final_missing_prediction_scores_zero():
    standings = TourFinalStandings(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=4, kom_jersey_rider_id=5, youth_jersey_rider_id=6,
    )
    assert score_tour_final(None, standings, GC_CONFIG)["points"] == 0


def test_tour_final_jerseys_are_match_or_nothing():
    pred = _base_pre_tour()
    standings = TourFinalStandings(
        gc_1st_rider_id=1, gc_2nd_rider_id=2, gc_3rd_rider_id=3,
        sprint_jersey_rider_id=99, kom_jersey_rider_id=5, youth_jersey_rider_id=88,
    )
    result = score_tour_final(pred, standings, GC_CONFIG)
    # Exact: gc 50+35+25=110, kom 30. Sprint/youth miss.
    assert result["points"] == 140
    assert result["breakdown"]["sprint_jersey"]["match"] is False
    assert result["breakdown"]["kom_jersey"]["match"] is True
    assert result["breakdown"]["youth_jersey"]["match"] is False
