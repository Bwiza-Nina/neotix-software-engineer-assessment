from io import BytesIO

from tests.conftest import login


CLEAN_CSV = """episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality
EP-10001,arm-01,pick cup,2026-08-01T10:00:00,40,Aline,good
EP-10002,arm-01,pick cup,2026-08-01T11:00:00,41,Eric,usable
EP-10003,arm-02,pick cup,2026-08-01T12:00:00,42,Diane,bad
EP-10004,arm-03,wipe table,2026-08-01T13:00:00,43,Jeanne,good
"""


def _import(client, headers, csv_text=CLEAN_CSV):
    return client.post(
        "/api/episodes/import",
        headers=headers,
        files={"file": ("episodes.csv", BytesIO(csv_text.encode()), "text/csv")},
    )


def test_status_transitions_and_assignment_rules(client):
    a = login(client, "client-a@example.com", "client123")
    ops = login(client, "ops1@example.com", "ops123")
    assert _import(client, ops).status_code == 200

    created = client.post(
        "/api/requests",
        headers=a,
        json={"task_name": "pick cup", "episodes_requested": 2, "deadline": "2026-12-01"},
    )
    request_id = created.json()["id"]
    assert created.json()["status"] == "submitted"
    assert created.json()["events"][0]["to_status"] == "submitted"

    skip = client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "delivered"})
    assert skip.status_code == 400

    start = client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "in_progress"})
    assert start.status_code == 200
    assert start.json()["status"] == "in_progress"

    bad = client.post(
        f"/api/requests/{request_id}/assignments",
        headers=ops,
        json={"episode_ids": ["EP-10003"]},
    )
    assert bad.status_code == 400
    assert "quality" in bad.json()["detail"]

    assign = client.post(
        f"/api/requests/{request_id}/assignments",
        headers=ops,
        json={"episode_ids": ["EP-10001"]},
    )
    assert assign.status_code == 200
    assert assign.json()["assigned_count"] == 1

    too_soon = client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "delivered"})
    assert too_soon.status_code == 400
    assert "Need at least" in too_soon.json()["detail"]

    other = client.post(
        "/api/requests",
        headers=a,
        json={"task_name": "wipe table", "episodes_requested": 1, "deadline": "2026-12-01"},
    )
    other_id = other.json()["id"]
    client.post(f"/api/requests/{other_id}/transition", headers=ops, json={"status": "in_progress"})
    stolen = client.post(
        f"/api/requests/{other_id}/assignments",
        headers=ops,
        json={"episode_ids": ["EP-10001"]},
    )
    assert stolen.status_code == 400
    assert "already assigned" in stolen.json()["detail"]

    fill = client.post(
        f"/api/requests/{request_id}/assignments",
        headers=ops,
        json={"episode_ids": ["EP-10002"]},
    )
    assert fill.json()["assigned_count"] == 2

    delivered = client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "delivered"})
    assert delivered.status_code == 200

    client_cannot_start = client.post(
        f"/api/requests/{request_id}/transition", headers=a, json={"status": "in_progress"}
    )
    assert client_cannot_start.status_code == 400

    rejected = client.post(f"/api/requests/{request_id}/transition", headers=a, json={"status": "rejected"})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    rework = client.post(f"/api/requests/{request_id}/transition", headers=ops, json={"status": "in_progress"})
    assert rework.status_code == 200

    delivered_again = client.post(
        f"/api/requests/{request_id}/transition", headers=ops, json={"status": "delivered"}
    )
    assert delivered_again.status_code == 200
    accepted = client.post(f"/api/requests/{request_id}/transition", headers=a, json={"status": "accepted"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    actors = {e["actor_id"] for e in accepted.json()["events"]}
    assert len(actors) >= 2
