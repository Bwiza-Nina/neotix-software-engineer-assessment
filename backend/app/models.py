from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, Enum):
    client = "client"
    operator = "operator"
    admin = "admin"


class Quality(str, Enum):
    good = "good"
    usable = "usable"
    bad = "bad"


class RequestStatus(str, Enum):
    submitted = "submitted"
    in_progress = "in_progress"
    delivered = "delivered"
    accepted = "accepted"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    organisation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    requests: Mapped[list["DatasetRequest"]] = relationship(back_populates="client")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        CheckConstraint("duration_seconds > 0", name="ck_episode_duration_positive"),
        CheckConstraint(
            "quality IN ('good', 'usable', 'bad')",
            name="ck_episode_quality",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    robot_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quality: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assignment: Mapped["Assignment | None"] = relationship(back_populates="episode", uselist=False)


class DatasetRequest(Base):
    __tablename__ = "dataset_requests"
    __table_args__ = (
        CheckConstraint("episodes_requested > 0", name="ck_request_count_positive"),
        CheckConstraint(
            "status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')",
            name="ck_request_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    episodes_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RequestStatus.submitted.value, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    client: Mapped[User] = relationship(back_populates="requests")
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="StatusEvent.created_at"
    )


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("episode_pk", name="uq_assignment_episode"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("dataset_requests.id"), nullable=False, index=True)
    episode_pk: Mapped[int] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    request: Mapped[DatasetRequest] = relationship(back_populates="assignments")
    episode: Mapped[Episode] = relationship(back_populates="assignment")
    assigned_by: Mapped[User] = relationship()


class StatusEvent(Base):
    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("dataset_requests.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    request: Mapped[DatasetRequest] = relationship(back_populates="events")
    actor: Mapped[User] = relationship()
