from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import DatasetRequest, RequestStatus, StatusEvent, User

# Clients own accept/reject. Operators (and admins) own everything else.
OPERATOR_TRANSITIONS = {
    RequestStatus.submitted: {RequestStatus.in_progress},
    RequestStatus.in_progress: {RequestStatus.delivered},
    RequestStatus.rejected: {RequestStatus.in_progress},
}
CLIENT_TRANSITIONS = {
    RequestStatus.delivered: {RequestStatus.accepted, RequestStatus.rejected},
}


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def assigned_count(request: DatasetRequest) -> int:
    return len(request.assignments)


def apply_transition(db: Session, request: DatasetRequest, actor: User, to_status: RequestStatus) -> DatasetRequest:
    current = RequestStatus(request.status)
    if current == to_status:
        raise DomainError(f"Request is already {current.value}")

    if actor.role == "client":
        allowed = CLIENT_TRANSITIONS.get(current, set())
        if to_status not in allowed:
            raise DomainError("Clients can only accept or reject a delivered request")
        if request.client_id != actor.id:
            raise DomainError("You can only act on your own requests", status_code=403)
    elif actor.role in ("operator", "admin"):
        allowed = OPERATOR_TRANSITIONS.get(current, set())
        if to_status not in allowed:
            raise DomainError(f"Operators cannot move a request from {current.value} to {to_status.value}")
    else:
        raise DomainError("Unknown role", status_code=403)

    if to_status == RequestStatus.delivered and assigned_count(request) < request.episodes_requested:
        raise DomainError(
            f"Need at least {request.episodes_requested} assigned episodes before delivery "
            f"(currently {assigned_count(request)})"
        )

    event = StatusEvent(
        request_id=request.id,
        from_status=current.value,
        to_status=to_status.value,
        actor_id=actor.id,
    )
    request.status = to_status.value
    request.updated_at = datetime.now(timezone.utc)
    db.add(event)
    db.flush()
    return request
