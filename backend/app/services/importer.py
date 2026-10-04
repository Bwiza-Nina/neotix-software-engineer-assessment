from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import IO

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Episode

KNOWN_ROBOTS = frozenset({"arm-01", "arm-02", "arm-03", "mobile-01", "humanoid-01"})
VALID_QUALITY = frozenset({"good", "usable", "bad"})
MAX_DURATION_SECONDS = 600  # 10 minutes; seed clips are 8–120s
REQUIRED_COLUMNS = (
    "episode_id",
    "robot_id",
    "task_name",
    "recorded_at",
    "duration_seconds",
    "operator_name",
    "quality",
)

DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
)


@dataclass
class Skip:
    row_number: int
    episode_id: str | None
    reason: str


@dataclass
class ParsedEpisode:
    episode_id: str
    robot_id: str
    task_name: str
    recorded_at: datetime
    duration_seconds: int
    operator_name: str
    quality: str


@dataclass
class ImportReport:
    imported: int = 0
    skipped: list[Skip] = field(default_factory=list)


def _blank(value: str | None) -> bool:
    return value is None or str(value).strip() == ""


def _norm_id(value: str) -> str:
    return value.strip().upper()


def _norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _parse_recorded_at(raw: str) -> datetime | None:
    text = raw.strip()
    if text.endswith("Z") and "T" in text:
        text_no_z = text[:-1]
        try:
            dt = datetime.strptime(text_no_z, "%Y-%m-%dT%H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _parse_duration(raw: str) -> int | None:
    text = raw.strip()
    if text.upper() in {"N/A", "NA", "NULL"}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    rounded = int(round(value))
    if rounded <= 0 or rounded > MAX_DURATION_SECONDS:
        return None
    return rounded


def parse_row(row: dict, row_number: int) -> ParsedEpisode | Skip:
    if any(col not in row for col in REQUIRED_COLUMNS):
        return Skip(row_number, None, "malformed row: missing columns")

    if _blank(row.get("episode_id")):
        return Skip(row_number, None, "missing episode_id")

    episode_id = _norm_id(row["episode_id"])
    if not re.fullmatch(r"EP-\d+", episode_id):
        return Skip(row_number, episode_id, "episode_id is not in EP-##### form")

    if _blank(row.get("robot_id")):
        return Skip(row_number, episode_id, "missing robot_id")
    robot_id = row["robot_id"].strip().lower()
    if robot_id not in KNOWN_ROBOTS:
        return Skip(row_number, episode_id, f"unknown robot_id '{robot_id}'")

    if _blank(row.get("task_name")):
        return Skip(row_number, episode_id, "missing task_name")
    task_name = _norm_space(row["task_name"]).lower()

    if _blank(row.get("recorded_at")):
        return Skip(row_number, episode_id, "missing recorded_at")
    recorded_at = _parse_recorded_at(row["recorded_at"])
    if recorded_at is None:
        return Skip(row_number, episode_id, "unparseable recorded_at")
    now = datetime.now(timezone.utc)
    if recorded_at > now:
        return Skip(row_number, episode_id, "recorded_at is in the future")

    if _blank(row.get("duration_seconds")):
        return Skip(row_number, episode_id, "missing duration_seconds")
    duration = _parse_duration(row["duration_seconds"])
    if duration is None:
        return Skip(row_number, episode_id, "invalid duration_seconds")

    if _blank(row.get("operator_name")):
        return Skip(row_number, episode_id, "missing operator_name")
    operator_name = _norm_space(row["operator_name"])

    if _blank(row.get("quality")):
        return Skip(row_number, episode_id, "missing quality")
    quality = row["quality"].strip().lower()
    if quality not in VALID_QUALITY:
        return Skip(row_number, episode_id, f"invalid quality '{quality}'")

    return ParsedEpisode(
        episode_id=episode_id,
        robot_id=robot_id,
        task_name=task_name,
        recorded_at=recorded_at,
        duration_seconds=duration,
        operator_name=operator_name,
        quality=quality,
    )


def parse_csv(content: str | bytes) -> tuple[list[ParsedEpisode], list[Skip]]:
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return [], [Skip(1, None, "file has no header row")]

    accepted: list[ParsedEpisode] = []
    skipped: list[Skip] = []
    seen_in_file: set[str] = set()

    for i, row in enumerate(reader, start=2):
        if row is None or all(_blank(v) for v in row.values()):
            continue
        result = parse_row(row, i)
        if isinstance(result, Skip):
            skipped.append(result)
            continue
        if result.episode_id in seen_in_file:
            skipped.append(Skip(i, result.episode_id, "duplicate episode_id in file (first row wins)"))
            continue
        seen_in_file.add(result.episode_id)
        accepted.append(result)
    return accepted, skipped


def import_episodes(db: Session, file_obj: IO[bytes]) -> ImportReport:
    content = file_obj.read()
    accepted, skipped = parse_csv(content)
    report = ImportReport(skipped=skipped)

    if not accepted:
        return report

    existing = set(
        db.scalars(select(Episode.episode_id).where(Episode.episode_id.in_([e.episode_id for e in accepted]))).all()
    )
    to_insert = []
    for row in accepted:
        if row.episode_id in existing:
            report.skipped.append(Skip(0, row.episode_id, "already imported (idempotent skip)"))
            continue
        to_insert.append(
            {
                "episode_id": row.episode_id,
                "robot_id": row.robot_id,
                "task_name": row.task_name,
                "recorded_at": row.recorded_at,
                "duration_seconds": row.duration_seconds,
                "operator_name": row.operator_name,
                "quality": row.quality,
            }
        )

    if to_insert:
        stmt = insert(Episode).values(to_insert).on_conflict_do_nothing(index_elements=["episode_id"])
        db.execute(stmt)
        report.imported = len(to_insert)
        db.flush()
    return report
