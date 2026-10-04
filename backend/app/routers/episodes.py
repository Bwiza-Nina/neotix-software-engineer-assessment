from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DbDep, OperatorUser
from app.models import Assignment, Episode
from app.schemas import EpisodeOut, ImportResult, ImportSkip
from app.services.importer import import_episodes

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def serialize_episode(episode: Episode) -> EpisodeOut:
    assigned_id = episode.assignment.request_id if episode.assignment else None
    return EpisodeOut(
        id=episode.id,
        episode_id=episode.episode_id,
        robot_id=episode.robot_id,
        task_name=episode.task_name,
        recorded_at=episode.recorded_at,
        duration_seconds=episode.duration_seconds,
        operator_name=episode.operator_name,
        quality=episode.quality,
        assigned_request_id=assigned_id,
    )


@router.get("", response_model=list[EpisodeOut])
def list_episodes(
    _: OperatorUser,
    db: DbDep,
    task_name: str | None = None,
    quality: str | None = None,
    unassigned_only: bool = False,
    limit: int = Query(default=200, le=1000),
) -> list[EpisodeOut]:
    stmt = select(Episode).options(selectinload(Episode.assignment)).order_by(Episode.recorded_at.desc()).limit(limit)
    if task_name:
        stmt = stmt.where(Episode.task_name == task_name.strip().lower())
    if quality:
        stmt = stmt.where(Episode.quality == quality.strip().lower())
    if unassigned_only:
        stmt = stmt.outerjoin(Assignment).where(Assignment.id.is_(None))
    return [serialize_episode(e) for e in db.scalars(stmt).unique().all()]


@router.post("/import", response_model=ImportResult)
def import_csv(_: OperatorUser, db: DbDep, file: UploadFile = File(...)) -> ImportResult:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")
    report = import_episodes(db, file.file)
    db.commit()
    return ImportResult(
        imported=report.imported,
        skipped=len(report.skipped),
        skipped_details=[
            ImportSkip(row_number=s.row_number, episode_id=s.episode_id, reason=s.reason)
            for s in report.skipped
        ],
    )
