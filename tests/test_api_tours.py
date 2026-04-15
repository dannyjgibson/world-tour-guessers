from __future__ import annotations


def _create_tour(client, slug="tdf-2024"):
    r = client.post(
        "/tours",
        json={"name": "Tour de France", "year": 2024, "pcs_slug": slug},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list_tour(client):
    tour = _create_tour(client)
    assert tour["name"] == "Tour de France"
    assert tour["year"] == 2024
    assert tour["pcs_slug"] == "tdf-2024"

    r = client.get("/tours")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_duplicate_pcs_slug_rejected(client):
    _create_tour(client, slug="tdf-2024")
    r = client.post(
        "/tours",
        json={"name": "Tour de France", "year": 2024, "pcs_slug": "tdf-2024"},
    )
    assert r.status_code == 409


def test_manual_stage_and_classify(client):
    tour = _create_tour(client)
    r = client.post(
        f"/tours/{tour['id']}/stages",
        json={"stage_number": 1, "name": "Lille ITT"},
    )
    assert r.status_code == 201
    stage = r.json()
    assert stage["stage_number"] == 1

    # Duplicate stage number is a conflict.
    r = client.post(f"/tours/{tour['id']}/stages", json={"stage_number": 1})
    assert r.status_code == 409

    # Classification.
    r = client.post(
        f"/tours/{tour['id']}/stages/{stage['id']}/classify",
        json={"stage_type": "tt"},
    )
    assert r.status_code == 200
    assert r.json()["classified_type"] == "tt"


def test_manual_stage_results_populate_winner_and_jerseys(client):
    tour = _create_tour(client)
    r = client.post(f"/tours/{tour['id']}/stages", json={"stage_number": 1})
    stage_id = r.json()["id"]

    # Create riders by adding them manually to the tour.
    for name in ["Pogačar", "Vingegaard", "Evenepoel"]:
        client.post(f"/tours/{tour['id']}/riders", params={"name": name})

    # We know the rider IDs will be 1,2,3 in creation order.
    payload = {
        "winner_rider_id": 1,
        "yellow_jersey_rider_id": 1,
        "green_jersey_rider_id": 2,
        "polka_dot_jersey_rider_id": 3,
        "white_jersey_rider_id": 1,
        "results": [
            {"rider_id": 1, "position": 1, "time_seconds": 10000},
            {"rider_id": 2, "position": 2, "time_seconds": 10005},
            {"rider_id": 3, "position": 3, "time_seconds": 10010},
        ],
    }
    r = client.post(
        f"/tours/{tour['id']}/stages/{stage_id}/results-manual",
        json=payload,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["winner_rider_id"] == 1
    assert data["yellow_jersey_rider_id"] == 1
    assert data["polka_dot_jersey_rider_id"] == 3


def test_manual_results_reject_duplicates(client):
    tour = _create_tour(client)
    r = client.post(f"/tours/{tour['id']}/stages", json={"stage_number": 1})
    stage_id = r.json()["id"]
    for name in ["A", "B"]:
        client.post(f"/tours/{tour['id']}/riders", params={"name": name})

    payload = {
        "results": [
            {"rider_id": 1, "position": 1},
            {"rider_id": 1, "position": 2},
        ]
    }
    r = client.post(
        f"/tours/{tour['id']}/stages/{stage_id}/results-manual",
        json=payload,
    )
    assert r.status_code == 400
