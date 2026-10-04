from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, DatasetRequest, Episode, Quality, RequestStatus, User
from app.services.workflow import DomainError

ASSIGNABLE_QUALITY = {Quality.good.value, Quality.usable.value}
ASSIGNABLE_STATUSES = {RequestStatus.submitted.value, RequestStatus.in_progress.value, RequestStatus.rejected.value}


def assign_episodes(db: Session, request: DatasetRequest, actor: User, episode_ids: list[str]) -> DatasetRequest:
    if request.status not in ASSIGNABLE_STATUSES:
        raise DomainError("Episodes can only be assigned while a request is open for work")

    unique_ids = list(dict.fromkeys(eid.strip().upper() for eid in episode_ids))
    episodes = db.scalars(select(Episode).where(Episode.episode_id.in_(unique_ids))).all()
    found = {e.episode_id: e for e in episodes}
    missing = [eid for eid in unique_ids if eid not in found]
    if missing:
        raise DomainError(f"Unknown episode ids: {', '.join(missing)}", status_code=404)

    already_on_this = {a.episode.episode_id for a in request.assignments}

    for eid in unique_ids:
        if eid in already_on_this:
            continue
        episode = found[eid]
        if episode.quality not in ASSIGNABLE_QUALITY:
            raise DomainError(f"{eid} is quality '{episode.quality}' and cannot be assigned")
        if episode.assignment is not None:
            raise DomainError(f"{eid} is already assigned to request {episode.assignment.request_id}")
        db.add(
            Assignment(
                request_id=request.id,
                episode_pk=episode.id,
                assigned_by_id=actor.id,
            )
        )
    db.flush()
    db.refresh(request)
    return request


def unassign_episodes(db: Session, request: DatasetRequest, episode_ids: list[str]) -> DatasetRequest:
    if request.status in {RequestStatus.delivered.value, RequestStatus.accepted.value}:
        raise DomainError("Cannot unassign episodes after delivery")

    wanted = {eid.strip().upper() for eid in episode_ids}
    for assignment in list(request.assignments):
        if assignment.episode.episode_id in wanted:
            db.delete(assignment)
    db.flush()
    db.refresh(request)
    return request
