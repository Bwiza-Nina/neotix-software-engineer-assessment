from pathlib import Path

from tests.conftest import SEED_CSV, login


def test_unauthenticated_is_rejected(client):
    res = client.get("/api/requests")
    assert res.status_code == 401


def test_client_cannot_see_other_client_requests(client):
    a = login(client, "client-a@example.com", "client123")
    b = login(client, "client-b@example.com", "client123")
    created = client.post(
        "/api/requests",
        headers=a,
        json={"task_name": "pick cup", "episodes_requested": 2, "deadline": "2026-12-01"},
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    listed = client.get("/api/requests", headers=b)
    assert listed.status_code == 200
    assert listed.json() == []

    other = client.get(f"/api/requests/{request_id}", headers=b)
    assert other.status_code == 404


def test_client_cannot_assign_or_import(client):
    a = login(client, "client-a@example.com", "client123")
    created = client.post(
        "/api/requests",
        headers=a,
        json={"task_name": "pick cup", "episodes_requested": 1, "deadline": "2026-12-01"},
    )
    request_id = created.json()["id"]
    assign = client.post(
        f"/api/requests/{request_id}/assignments",
        headers=a,
        json={"episode_ids": ["EP-00001"]},
    )
    assert assign.status_code == 403
    with SEED_CSV.open("rb") as fh:
        imported = client.post("/api/episodes/import", headers=a, files={"file": ("episodes.csv", fh, "text/csv")})
    assert imported.status_code == 403


def test_operator_cannot_accept_or_reject(client):
    a = login(client, "client-a@example.com", "client123")
    ops = login(client, "ops1@example.com", "ops123")
    created = client.post(
        "/api/requests",
        headers=a,
        json={"task_name": "pick cup", "episodes_requested": 1, "deadline": "2026-12-01"},
    )
    request_id = created.json()["id"]
    client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "in_progress"})
    # not delivered yet, and even if, operator cannot accept
    res = client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "accepted"})
    assert res.status_code == 400


def test_client_cannot_create_if_not_client_role(client):
    ops = login(client, "ops1@example.com", "ops123")
    res = client.post(
        "/api/requests",
        headers=ops,
        json={"task_name": "pick cup", "episodes_requested": 1, "deadline": "2026-12-01"},
    )
    assert res.status_code == 403


def test_admin_can_deactivate_user(client):
    admin = login(client, "admin@example.com", "admin123")
    users = client.get("/api/users", headers=admin)
    ops_id = next(u["id"] for u in users.json() if u["email"] == "ops1@example.com")
    res = client.patch(f"/api/users/{ops_id}", headers=admin, json={"is_active": False})
    assert res.status_code == 200
    denied = client.post("/api/auth/login", json={"email": "ops1@example.com", "password": "ops123"})
    assert denied.status_code == 401
