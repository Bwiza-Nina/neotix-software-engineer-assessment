from io import BytesIO
from pathlib import Path

from tests.conftest import SEED_CSV, login


def test_seed_csv_import_is_idempotent(client):
    ops = login(client, "ops1@example.com", "ops123")
    with SEED_CSV.open("rb") as fh:
        first = client.post("/api/episodes/import", headers=ops, files={"file": ("episodes.csv", fh, "text/csv")})
    assert first.status_code == 200
    body = first.json()
    assert body["imported"] > 0
    assert body["skipped"] > 0
    reasons = {row["reason"] for row in body["skipped_details"]}
    assert any("duplicate" in r or "already imported" in r or "missing" in r or "invalid" in r for r in reasons)

    with SEED_CSV.open("rb") as fh:
        second = client.post("/api/episodes/import", headers=ops, files={"file": ("episodes.csv", fh, "text/csv")})
    assert second.status_code == 200
    assert second.json()["imported"] == 0
    assert second.json()["skipped"] >= body["imported"] + body["skipped"]

    listed = client.get("/api/episodes", headers=ops, params={"limit": 1000})
    ids = [e["episode_id"] for e in listed.json()]
    assert len(ids) == len(set(ids))
    assert all(e["quality"] in {"good", "usable", "bad"} for e in listed.json())


def test_analytics_runs_in_sql(client):
    ops = login(client, "ops1@example.com", "ops123")
    csv = """episode_id,robot_id,task_name,recorded_at,duration_seconds,operator_name,quality
EP-20001,arm-01,pick cup,2026-08-01T10:00:00,40,Aline,good
EP-20002,arm-01,pick cup,2026-08-01T11:00:00,41,Eric,good
EP-20003,arm-02,wipe table,2026-08-02T12:00:00,42,Diane,usable
"""
    res = client.post(
        "/api/episodes/import",
        headers=ops,
        files={"file": ("e.csv", BytesIO(csv.encode()), "text/csv")},
    )
    assert res.status_code == 200
    analytics = client.get("/api/analytics", headers=ops, params={"start": "2026-08-01", "end": "2026-08-31"})
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["top_5_tasks_by_good_episodes"][0]["task_name"] == "pick cup"
    assert body["top_5_tasks_by_good_episodes"][0]["good_count"] == 2
