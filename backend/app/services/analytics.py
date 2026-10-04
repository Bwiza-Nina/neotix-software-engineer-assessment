from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


def analytics(db: Session, start: date, end: date) -> dict:
    """All three analytics slices are computed in SQL, not in Python loops."""
    per_day = db.execute(
        text(
            """
            SELECT recorded_at::date AS day, robot_id, COUNT(*) AS episode_count
            FROM episodes
            WHERE recorded_at::date BETWEEN :start AND :end
            GROUP BY day, robot_id
            ORDER BY day, robot_id
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()

    by_status = db.execute(
        text(
            """
            SELECT status, COUNT(*) AS request_count
            FROM dataset_requests
            WHERE created_at::date BETWEEN :start AND :end
            GROUP BY status
            ORDER BY status
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()

    median_row = db.execute(
        text(
            """
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM (delivered_at - submitted_at)))
                   / 3600.0 AS median_hours
            FROM (
                SELECT
                    MIN(CASE WHEN to_status = 'submitted' THEN created_at END) AS submitted_at,
                    MIN(CASE WHEN to_status = 'delivered' THEN created_at END) AS delivered_at
                FROM status_events
                GROUP BY request_id
            ) t
            WHERE submitted_at IS NOT NULL
              AND delivered_at IS NOT NULL
              AND submitted_at::date BETWEEN :start AND :end
            """
        ),
        {"start": start, "end": end},
    ).one()

    top_tasks = db.execute(
        text(
            """
            SELECT task_name, COUNT(*) AS good_count
            FROM episodes
            WHERE quality = 'good'
              AND recorded_at::date BETWEEN :start AND :end
            GROUP BY task_name
            ORDER BY good_count DESC, task_name
            LIMIT 5
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()

    return {
        "episodes_recorded_per_day_per_robot": [dict(r) for r in per_day],
        "requests_by_status": [dict(r) for r in by_status],
        "median_submitted_to_delivered_hours": median_row[0],
        "top_5_tasks_by_good_episodes": [dict(r) for r in top_tasks],
    }
