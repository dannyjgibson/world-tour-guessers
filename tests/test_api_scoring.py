"""End-to-end test of the scoring flow through the HTTP layer."""
from __future__ import annotations

import pytest


@pytest.fixture
def scored_league(client):
    """Set up a league with 2 stages, 2 members, and both players submitted picks."""
    # Tour with 2 stages.
    tour = client.post(
        "/tours", json={"name": "Giro", "year": 2025, "pcs_slug": "giro-2025"}
    ).json()
    stage1 = client.post(f"/tours/{tour['id']}/stages", json={"stage_number": 1}).json()
    stage2 = client.post(f"/tours/{tour['id']}/stages", json={"stage_number": 2}).json()

    # Riders: IDs 1..5.
    for name in ["Pogačar", "Vingegaard", "Evenepoel", "Jakobsen", "Carapaz"]:
        client.post(f"/tours/{tour['id']}/riders", params={"name": name})

    # Users + league.
    alice = client.post("/users", json={"display_name": "Alice"}).json()
    bob = client.post("/users", json={"display_name": "Bob"}).json()
    league = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "L", "tour_id": tour["id"]},
    ).json()
    client.post(f"/leagues/{league['invite_code']}/join", params={"user_id": bob["id"]})

    # Pre-tour picks.
    pre_tour_alice = {
        "gc_1st_rider_id": 1,
        "gc_2nd_rider_id": 2,
        "gc_3rd_rider_id": 3,
        "sprint_jersey_rider_id": 4,
        "kom_jersey_rider_id": 5,
        "youth_jersey_rider_id": 1,
    }
    pre_tour_bob = {
        "gc_1st_rider_id": 2,  # different GC1 from Alice
        "gc_2nd_rider_id": 1,
        "gc_3rd_rider_id": 3,
        "sprint_jersey_rider_id": 4,
        "kom_jersey_rider_id": 3,
        "youth_jersey_rider_id": 1,
    }
    client.post(
        f"/leagues/{league['id']}/predictions/pre-tour",
        params={"user_id": alice["id"]},
        json=pre_tour_alice,
    )
    client.post(
        f"/leagues/{league['id']}/predictions/pre-tour",
        params={"user_id": bob["id"]},
        json=pre_tour_bob,
    )

    # Stage 1 picks — Alice right, Bob wrong.
    client.post(
        f"/leagues/{league['id']}/predictions/stage",
        params={"user_id": alice["id"]},
        json={"stage_id": stage1["id"], "rider_id": 1, "stage_type": "sprint"},
    )
    client.post(
        f"/leagues/{league['id']}/predictions/stage",
        params={"user_id": bob["id"]},
        json={"stage_id": stage1["id"], "rider_id": 3, "stage_type": "gc"},
    )

    return {
        "tour_id": tour["id"],
        "stage1_id": stage1["id"],
        "stage2_id": stage2["id"],
        "league_id": league["id"],
        "alice_id": alice["id"],
        "bob_id": bob["id"],
    }


def test_score_stage_requires_classification(client, scored_league):
    ctx = scored_league
    # Results entered, but not classified yet.
    client.post(
        f"/tours/{ctx['tour_id']}/stages/{ctx['stage1_id']}/results-manual",
        json={
            "winner_rider_id": 1,
            "yellow_jersey_rider_id": 1,
            "green_jersey_rider_id": 4,
            "polka_dot_jersey_rider_id": 5,
            "white_jersey_rider_id": 1,
            "results": [{"rider_id": 1, "position": 1}],
        },
    )
    r = client.post(f"/leagues/{ctx['league_id']}/score-stage/{ctx['stage1_id']}")
    assert r.status_code == 400


def test_score_stage_end_to_end(client, scored_league):
    ctx = scored_league
    tour_id = ctx["tour_id"]
    stage_id = ctx["stage1_id"]

    # Import results manually and classify.
    client.post(
        f"/tours/{tour_id}/stages/{stage_id}/results-manual",
        json={
            "winner_rider_id": 1,  # Pogačar wins
            "yellow_jersey_rider_id": 1,  # yellow = Pogačar
            "green_jersey_rider_id": 4,   # green = Jakobsen (Alice's pick)
            "polka_dot_jersey_rider_id": 5,  # polka = Carapaz (Alice's pick)
            "white_jersey_rider_id": 1,
            "results": [
                {"rider_id": 1, "position": 1},
                {"rider_id": 2, "position": 2},
                {"rider_id": 3, "position": 3},
            ],
        },
    )
    client.post(
        f"/tours/{tour_id}/stages/{stage_id}/classify",
        json={"stage_type": "sprint"},
    )
    r = client.post(f"/leagues/{ctx['league_id']}/score-stage/{stage_id}")
    assert r.status_code == 200, r.text
    by_user = {s["user_id"]: s for s in r.json()}

    # Alice: picked rider 1 + sprint → 25 + 10 = 35 stage pick.
    # Running bonus: yellow (GC1=1, holder=1) +3; green (pick=4, holder=4) +2;
    # polka (pick=5, holder=5) +2; white (pick=1, holder=1) +1. Total 8.
    alice = by_user[ctx["alice_id"]]
    assert alice["stage_pick_points"] == 35
    assert alice["running_bonus_points"] == 8
    assert alice["total_points"] == 43

    # Bob: picked rider 3 + gc, stage was rider 1 sprint → 0 stage pick.
    # Running bonus: GC1=2 (holder=1, no match); green (4==4) +2; polka (3, holder=5, no) 0;
    # white (1==1) +1. Total 3.
    bob = by_user[ctx["bob_id"]]
    assert bob["stage_pick_points"] == 0
    assert bob["running_bonus_points"] == 3
    assert bob["total_points"] == 3

    # Leaderboard reflects totals.
    r = client.get(f"/leagues/{ctx['league_id']}/leaderboard")
    entries = {e["user_id"]: e for e in r.json()["entries"]}
    assert entries[ctx["alice_id"]]["total_points"] == 43
    assert entries[ctx["bob_id"]]["total_points"] == 3
    # Sorted: Alice first.
    assert r.json()["entries"][0]["user_id"] == ctx["alice_id"]


def test_score_stage_is_idempotent(client, scored_league):
    ctx = scored_league
    tour_id = ctx["tour_id"]
    stage_id = ctx["stage1_id"]

    client.post(
        f"/tours/{tour_id}/stages/{stage_id}/results-manual",
        json={
            "winner_rider_id": 1,
            "yellow_jersey_rider_id": 1,
            "green_jersey_rider_id": 4,
            "polka_dot_jersey_rider_id": 5,
            "white_jersey_rider_id": 1,
            "results": [{"rider_id": 1, "position": 1}],
        },
    )
    client.post(f"/tours/{tour_id}/stages/{stage_id}/classify", json={"stage_type": "sprint"})

    # First run.
    r1 = client.post(f"/leagues/{ctx['league_id']}/score-stage/{stage_id}").json()
    # Second run (idempotent).
    r2 = client.post(f"/leagues/{ctx['league_id']}/score-stage/{stage_id}").json()

    by_user_1 = {s["user_id"]: s["total_points"] for s in r1}
    by_user_2 = {s["user_id"]: s["total_points"] for s in r2}
    assert by_user_1 == by_user_2

    # And only one Score row per user exists.
    r = client.get(f"/leagues/{ctx['league_id']}/scores/{stage_id}")
    assert len({s["user_id"] for s in r.json()}) == len(r.json())


def test_tour_final_scoring(client, scored_league):
    ctx = scored_league
    # Set final standings.
    client.post(
        f"/tours/{ctx['tour_id']}/final-standings",
        json={
            "gc_1st_rider_id": 1,
            "gc_2nd_rider_id": 2,
            "gc_3rd_rider_id": 3,
            "sprint_jersey_rider_id": 4,
            "kom_jersey_rider_id": 5,
            "youth_jersey_rider_id": 1,
        },
    )
    r = client.post(f"/leagues/{ctx['league_id']}/score-tour-final")
    assert r.status_code == 200, r.text
    by_user = {s["user_id"]: s for s in r.json()}

    # Alice had exact podium + exact sprint + exact kom + exact youth = 50+35+25+30+30+20=190.
    assert by_user[ctx["alice_id"]]["tour_final_points"] == 190
    # Bob: gc_1st=2 actual 1 → miss; 2 is on podium so gc_1st earns gc_on_podium (10).
    # gc_2nd=1 actual 2 → 1 is on podium → gc_on_podium (10).
    # gc_3rd=3 actual 3 → exact 25.
    # sprint=4 → exact 30. kom=3 actual 5 → miss. youth=1 → exact 20.
    # Total: 10 + 10 + 25 + 30 + 0 + 20 = 95.
    assert by_user[ctx["bob_id"]]["tour_final_points"] == 95

    # Score row is attached to the final stage (stage2 here).
    for s in r.json():
        assert s["stage_id"] == ctx["stage2_id"]


def test_tour_final_requires_standings_set(client, scored_league):
    ctx = scored_league
    r = client.post(f"/leagues/{ctx['league_id']}/score-tour-final")
    assert r.status_code == 400


def test_user_stage_score_detail_endpoint(client, scored_league):
    ctx = scored_league
    client.post(
        f"/tours/{ctx['tour_id']}/stages/{ctx['stage1_id']}/results-manual",
        json={
            "winner_rider_id": 1,
            "yellow_jersey_rider_id": 1,
            "green_jersey_rider_id": 4,
            "polka_dot_jersey_rider_id": 5,
            "white_jersey_rider_id": 1,
            "results": [{"rider_id": 1, "position": 1}],
        },
    )
    client.post(
        f"/tours/{ctx['tour_id']}/stages/{ctx['stage1_id']}/classify",
        json={"stage_type": "sprint"},
    )
    client.post(f"/leagues/{ctx['league_id']}/score-stage/{ctx['stage1_id']}")

    r = client.get(
        f"/leagues/{ctx['league_id']}/scores/{ctx['stage1_id']}/{ctx['alice_id']}"
    )
    assert r.status_code == 200
    body = r.json()
    assert "breakdown" in body
    assert body["breakdown"]["stage_picks"]["stage_winner_points"] == 25


def test_non_member_has_no_score(client, scored_league):
    ctx = scored_league
    r = client.get(
        f"/leagues/{ctx['league_id']}/scores/{ctx['stage1_id']}/9999"
    )
    assert r.status_code == 404
