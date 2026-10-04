from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    organisation: str | None
    is_active: bool


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=255)
    role: Literal["client", "operator", "admin"]
    organisation: str | None = None


class UserUpdateIn(BaseModel):
    role: Literal["client", "operator", "admin"] | None = None
    is_active: bool | None = None


class RequestCreateIn(BaseModel):
    task_name: str = Field(min_length=1, max_length=255)
    episodes_requested: int = Field(gt=0, le=100_000)
    deadline: date
    notes: str | None = None


class StatusEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: str | None
    to_status: str
    actor_id: int
    created_at: datetime


class EpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    episode_id: str
    robot_id: str
    task_name: str
    recorded_at: datetime
    duration_seconds: int
    operator_name: str
    quality: str
    assigned_request_id: int | None = None


class AssignmentOut(BaseModel):
    id: int
    episode: EpisodeOut
    assigned_by_id: int
    assigned_at: datetime


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_name: str | None = None
    task_name: str
    episodes_requested: int
    assigned_count: int = 0
    deadline: date
    notes: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    events: list[StatusEventOut] = []
    assignments: list[AssignmentOut] = []


class TransitionIn(BaseModel):
    status: Literal["in_progress", "delivered", "accepted", "rejected"]


class AssignIn(BaseModel):
    episode_ids: list[str] = Field(min_length=1)


class UnassignIn(BaseModel):
    episode_ids: list[str] = Field(min_length=1)


class ImportSkip(BaseModel):
    row_number: int
    episode_id: str | None
    reason: str


class ImportResult(BaseModel):
    imported: int
    skipped: int
    skipped_details: list[ImportSkip]


class AnalyticsOut(BaseModel):
    episodes_recorded_per_day_per_robot: list[dict]
    requests_by_status: list[dict]
    median_submitted_to_delivered_hours: float | None
    top_5_tasks_by_good_episodes: list[dict]
