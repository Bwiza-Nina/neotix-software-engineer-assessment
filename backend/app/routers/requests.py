from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import CurrentUser, DbDep, OperatorUser
from app.models import Assignment, DatasetRequest, Episode, RequestStatus, Role, StatusEvent
from app.schemas import (
    AssignIn,
    AssignmentOut,
    EpisodeOut,
    RequestCreateIn,
    RequestOut,
    StatusEventOut,
    TransitionIn,
    UnassignIn,
)
from app.services.assignments import assign_episodes, unassign_episodes
from app.services.events import publish
from app.services.workflow import DomainError, apply_transition, assigned_count

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _episode_out(episode: Episode, assigned_request_id: int | None = None) -> EpisodeOut:
    return EpisodeOut(
        id=episode.id,
        episode_id=episode.episode_id,
        robot_id=episode.robot_id,
        task_name=episode.task_name,
        recorded_at=episode.recorded_at,
        duration_seconds=episode.duration_seconds,
        operator_name=episode.operator_name,
        quality=episode.quality,
        assigned_request_id=assigned_request_id,
    )


def serialize_request(request: DatasetRequest) -> RequestOut:
    assignments = [
        AssignmentOut(
            id=a.id,
            episode=_episode_out(a.episode, assigned_request_id=request.id),
            assigned_by_id=a.assigned_by_id,
            assigned_at=a.assigned_at,
        )
        for a in request.assignments
    ]
    events = [StatusEventOut.model_validate(e) for e in request.events]
    return RequestOut(
        id=request.id,
        client_id=request.client_id,
        client_name=request.client.name if request.client else None,
        task_name=request.task_name,
        episodes_requested=request.episodes_requested,
        assigned_count=assigned_count(request),
        deadline=request.deadline,
        notes=request.notes,
        status=request.status,
        created_at=request.created_at,
        updated_at=request.updated_at,
        events=events,
        assignments=assignments,
    )


_REQUEST_LOAD = (
    selectinload(DatasetRequest.assignments).selectinload(Assignment.episode),
    selectinload(DatasetRequest.events),
    selectinload(DatasetRequest.client),
)


def _load(db, request_id: int) -> DatasetRequest | None:
    return db.scalar(
        select(DatasetRequest).options(*_REQUEST_LOAD).where(DatasetRequest.id == request_id)
    )


def _raise_domain(exc: DomainError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[RequestOut])
def list_requests(user: CurrentUser, db: DbDep) -> list[RequestOut]:
    stmt = (
        select(DatasetRequest)
        .options(*_REQUEST_LOAD)
        .order_by(DatasetRequest.created_at.desc())
    )
    if user.role == Role.client.value:
        stmt = stmt.where(DatasetRequest.client_id == user.id)
    return [serialize_request(r) for r in db.scalars(stmt).unique().all()]


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_request(user: CurrentUser, body: RequestCreateIn, db: DbDep) -> RequestOut:
    if user.role != Role.client.value:
        raise HTTPException(status_code=403, detail="Only clients can create dataset requests")
    request = DatasetRequest(
        client_id=user.id,
        task_name=body.task_name.strip().lower(),
        episodes_requested=body.episodes_requested,
        deadline=body.deadline,
        notes=body.notes,
        status=RequestStatus.submitted.value,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(request)
    db.flush()
    db.add(
        StatusEvent(
            request_id=request.id,
            from_status=None,
            to_status=RequestStatus.submitted.value,
            actor_id=user.id,
        )
    )
    db.commit()
    request = _load(db, request.id)
    publish({"type": "request.created", "request_id": request.id, "status": request.status})
    return serialize_request(request)


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, user: CurrentUser, db: DbDep) -> RequestOut:
    request = _load(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if user.role == Role.client.value and request.client_id != user.id:
        raise HTTPException(status_code=404, detail="Request not found")
    return serialize_request(request)


@router.post("/{request_id}/transition", response_model=RequestOut)
def transition(request_id: int, body: TransitionIn, user: CurrentUser, db: DbDep) -> RequestOut:
    request = _load(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if user.role == Role.client.value and request.client_id != user.id:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        apply_transition(db, request, user, RequestStatus(body.status))
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_domain(exc)
    request = _load(db, request_id)
    publish(
        {
            "type": "request.status",
            "request_id": request.id,
            "status": request.status,
            "actor_id": user.id,
        }
    )
    return serialize_request(request)


@router.post("/{request_id}/assignments", response_model=RequestOut)
def assign(request_id: int, body: AssignIn, user: OperatorUser, db: DbDep) -> RequestOut:
    request = _load(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        assign_episodes(db, request, user, body.episode_ids)
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_domain(exc)
    request = _load(db, request_id)
    publish({"type": "request.assigned", "request_id": request.id, "assigned_count": assigned_count(request)})
    return serialize_request(request)


@router.delete("/{request_id}/assignments", response_model=RequestOut)
def unassign(request_id: int, body: UnassignIn, user: OperatorUser, db: DbDep) -> RequestOut:
    request = _load(db, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    try:
        unassign_episodes(db, request, body.episode_ids)
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_domain(exc)
    request = _load(db, request_id)
    return serialize_request(request)
