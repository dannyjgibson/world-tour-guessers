from __future__ import annotations


def _setup_tour_and_users(client):
    tour = client.post(
        "/tours", json={"name": "Giro", "year": 2025, "pcs_slug": "giro-2025"}
    ).json()
    alice = client.post("/users", json={"display_name": "Alice"}).json()
    bob = client.post("/users", json={"display_name": "Bob"}).json()
    return tour, alice, bob


def test_create_league_generates_invite_code_and_applies_defaults(client):
    tour, alice, _ = _setup_tour_and_users(client)
    r = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "Fantasy Giro", "tour_id": tour["id"]},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["commissioner_id"] == alice["id"]
    assert len(data["invite_code"]) > 0
    # Commissioner is auto-added as a member.
    assert alice["id"] in data["member_ids"]
    cfg = data["scoring_config"]
    assert cfg["stage_scoring"]["stage_winner"] == 25
    assert cfg["gc_scoring"]["gc_exact_1st"] == 50
    assert cfg["running_bonus"]["yellow_jersey_per_stage"] == 3


def test_create_league_with_custom_scoring(client):
    tour, alice, _ = _setup_tour_and_users(client)
    r = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={
            "name": "Custom",
            "tour_id": tour["id"],
            "scoring_config": {
                "stage_scoring": {"stage_winner": 100, "stage_type": 50},
                "running_bonus": {"yellow_jersey_per_stage": 10},
            },
        },
    )
    assert r.status_code == 201
    cfg = r.json()["scoring_config"]
    assert cfg["stage_scoring"]["stage_winner"] == 100
    # Unspecified field falls back to default.
    assert cfg["gc_scoring"]["gc_exact_1st"] == 50


def test_join_league_via_invite_code(client):
    tour, alice, bob = _setup_tour_and_users(client)
    league = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "L", "tour_id": tour["id"]},
    ).json()

    r = client.post(
        f"/leagues/{league['invite_code']}/join",
        params={"user_id": bob["id"]},
    )
    assert r.status_code == 200
    assert bob["id"] in r.json()["member_ids"]

    # Joining again is a no-op (idempotent).
    r = client.post(
        f"/leagues/{league['invite_code']}/join",
        params={"user_id": bob["id"]},
    )
    assert r.status_code == 200


def test_join_league_bad_invite_code(client):
    _, _, bob = _setup_tour_and_users(client)
    r = client.post("/leagues/not-a-real-code/join", params={"user_id": bob["id"]})
    assert r.status_code == 404


def test_update_scoring_config_requires_commissioner(client):
    tour, alice, bob = _setup_tour_and_users(client)
    league = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "L", "tour_id": tour["id"]},
    ).json()

    r = client.put(
        f"/leagues/{league['id']}/scoring-config",
        params={"commissioner_id": bob["id"]},
        json={"stage_scoring": {"stage_winner": 1}},
    )
    assert r.status_code == 403

    r = client.put(
        f"/leagues/{league['id']}/scoring-config",
        params={"commissioner_id": alice["id"]},
        json={"stage_scoring": {"stage_winner": 1}},
    )
    assert r.status_code == 200
    assert r.json()["stage_scoring"]["stage_winner"] == 1


def test_prop_bet_crud_and_scoring(client):
    tour, alice, bob = _setup_tour_and_users(client)
    league = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "L", "tour_id": tour["id"]},
    ).json()
    # Bob joins.
    client.post(f"/leagues/{league['invite_code']}/join", params={"user_id": bob["id"]})

    r = client.post(
        f"/leagues/{league['id']}/prop-bets",
        params={"commissioner_id": alice["id"]},
        json={"question": "Combative?", "max_points": 20},
    )
    assert r.status_code == 201
    prop_id = r.json()["id"]

    # Bob submits an answer.
    r = client.post(
        f"/leagues/{league['id']}/predictions/prop-bet",
        params={"user_id": bob["id"]},
        json={"prop_bet_id": prop_id, "answer": "Wout van Aert"},
    )
    assert r.status_code == 200

    # Commissioner lists props and sees the answer.
    r = client.get(f"/leagues/{league['id']}/prop-bets")
    data = r.json()
    assert len(data) == 1
    assert len(data[0]["answers"]) == 1

    # Commissioner awards 15 points to Bob.
    r = client.post(
        f"/leagues/{league['id']}/prop-bets/{prop_id}/score",
        params={"commissioner_id": alice["id"]},
        json=[{"user_id": bob["id"], "points": 15}],
    )
    assert r.status_code == 200

    # Leaderboard reflects prop points.
    r = client.get(f"/leagues/{league['id']}/leaderboard")
    entries = {e["user_id"]: e for e in r.json()["entries"]}
    assert entries[bob["id"]]["prop_bet_points"] == 15
    assert entries[bob["id"]]["total_points"] == 15


def test_prop_bet_points_clamped_to_max(client):
    tour, alice, _ = _setup_tour_and_users(client)
    league = client.post(
        "/leagues",
        params={"commissioner_id": alice["id"]},
        json={"name": "L", "tour_id": tour["id"]},
    ).json()
    r = client.post(
        f"/leagues/{league['id']}/prop-bets",
        params={"commissioner_id": alice["id"]},
        json={"question": "Q", "max_points": 10},
    )
    prop_id = r.json()["id"]
    # Try to award 999 points — should clamp to 10.
    r = client.post(
        f"/leagues/{league['id']}/prop-bets/{prop_id}/score",
        params={"commissioner_id": alice["id"]},
        json=[{"user_id": alice["id"], "points": 999}],
    )
    assert r.status_code == 200
    r = client.get(f"/leagues/{league['id']}/leaderboard")
    entries = {e["user_id"]: e for e in r.json()["entries"]}
    assert entries[alice["id"]]["prop_bet_points"] == 10
