from __future__ import annotations


def test_create_and_list_users(client):
    r = client.post("/users", json={"display_name": "Alice"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["display_name"] == "Alice"
    user_id = data["id"]

    r = client.post("/users", json={"display_name": "Bob", "email": "bob@example.com"})
    assert r.status_code == 201

    r = client.get("/users")
    assert r.status_code == 200
    names = [u["display_name"] for u in r.json()]
    assert names == ["Alice", "Bob"]

    r = client.get(f"/users/{user_id}")
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alice"


def test_duplicate_display_name_rejected(client):
    client.post("/users", json={"display_name": "Alice"})
    r = client.post("/users", json={"display_name": "Alice"})
    assert r.status_code == 409


def test_missing_user_returns_404(client):
    r = client.get("/users/9999")
    assert r.status_code == 404
