from __future__ import annotations

import pytest


@pytest.fixture
def league_context(client):
    """A tour with 1 stage, 3 riders, 1 league, and members alice+bob."""
    tour = client.post(
        "/tours", json={"name": "Giro", "year": 2025, "pcs_slug": "giro-2025"}
    ).json()
    client.post(f"/tours/{tour['id']}/stages", json={"stage_number": 1})
    for name in ["Pogačar", "Vingegaard", "Evenepoel"]:
        client.post(f"/tours/{tour['id']}/riders", params={"name": name})

    alice = client.post("/users", json={"display_name": "Alice"}).json()
    bob = client.post("/users", json={"display_name": "Bob"}).json()
    league = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "L", "tour_id": tour["id"]},
    ).json()
    client.post(f"/leagues/{league['invite_code']}/join", params={"user_id": bob["id"]})

    return {
        "tour_id": tour["id"],
        "stage_id": 1,
        "league_id": league["id"],
        "invite_code": league["invite_code"],
        "alice": alice,
        "bob": bob,
    }


def test_stage_prediction_submit_and_upsert(client, league_context):
    ctx = league_context
    r = client.post(
        f"/leagues/{ctx['league_id']}/predictions/stage",
        params={"user_id": ctx["bob"]["id"]},
        json={"stage_id": ctx["stage_id"], "rider_id": 1, "stage_type": "sprint"},
    )
    assert r.status_code == 200
    pred_id = r.json()["id"]
    assert r.json()["rider_id"] == 1

    # Resubmitting upserts.
    r = client.post(
        f"/leagues/{ctx['league_id']}/predictions/stage",
        params={"user_id": ctx["bob"]["id"]},
        json={"stage_id": ctx["stage_id"], "rider_id": 2, "stage_type": "gc"},
    )
    assert r.status_code == 200
    assert r.json()["id"] == pred_id
    assert r.json()["rider_id"] == 2
    assert r.json()["stage_type"] == "gc"


def test_stage_prediction_rejects_non_member(client, league_context):
    charlie = client.post("/users", json={"display_name": "Charlie"}).json()
    ctx = league_context
    r = client.post(
        f"/leagues/{ctx['league_id']}/predictions/stage",
        params={"user_id": charlie["id"]},
        json={"stage_id": ctx["stage_id"], "rider_id": 1, "stage_type": "sprint"},
    )
    assert r.status_code == 403


def test_pre_tour_prediction_upsert(client, league_context):
    ctx = league_context
    payload = {
        "gc_1st_rider_id": 1,
        "gc_2nd_rider_id": 2,
        "gc_3rd_rider_id": 3,
        "sprint_jersey_rider_id": 2,
        "kom_jersey_rider_id": 3,
        "youth_jersey_rider_id": 1,
    }
    r = client.post(
        f"/leagues/{ctx['league_id']}/predictions/pre-tour",
        params={"user_id": ctx["bob"]["id"]},
        json=payload,
    )
    assert r.status_code == 200
    assert r.json()["gc_1st_rider_id"] == 1

    # Change the pick; should upsert.
    payload["gc_1st_rider_id"] = 2
    r = client.post(
        f"/leagues/{ctx['league_id']}/predictions/pre-tour",
        params={"user_id": ctx["bob"]["id"]},
        json=payload,
    )
    assert r.json()["gc_1st_rider_id"] == 2

    r = client.get(
        f"/leagues/{ctx['league_id']}/predictions/pre-tour",
        params={"user_id": ctx["bob"]["id"]},
    )
    assert r.json()["gc_1st_rider_id"] == 2


def test_stage_prediction_cross_tour_rejected(client, league_context):
    """Can't submit a pick for a stage that belongs to another tour."""
    ctx = league_context
    # Create a second tour with its own stage.
    other = client.post(
        "/tours", json={"name": "Vuelta", "year": 2025, "pcs_slug": "vuelta-2025"}
    ).json()
    other_stage = client.post(
        f"/tours/{other['id']}/stages", json={"stage_number": 1}
    ).json()

    r = client.post(
        f"/leagues/{ctx['league_id']}/predictions/stage",
        params={"user_id": ctx["bob"]["id"]},
        json={"stage_id": other_stage["id"], "rider_id": 1, "stage_type": "sprint"},
    )
    assert r.status_code == 400
