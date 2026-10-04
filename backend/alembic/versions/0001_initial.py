"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("organisation", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("episode_id", sa.String(64), nullable=False),
        sa.Column("robot_id", sa.String(64), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("operator_name", sa.String(255), nullable=False),
        sa.Column("quality", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("duration_seconds > 0", name="ck_episode_duration_positive"),
        sa.CheckConstraint("quality IN ('good', 'usable', 'bad')", name="ck_episode_quality"),
    )
    op.create_index("ix_episodes_episode_id", "episodes", ["episode_id"], unique=True)
    op.create_index("ix_episodes_robot_id", "episodes", ["robot_id"])
    op.create_index("ix_episodes_task_name", "episodes", ["task_name"])
    op.create_index("ix_episodes_recorded_at", "episodes", ["recorded_at"])
    op.create_index("ix_episodes_quality", "episodes", ["quality"])
    op.create_index("ix_episodes_recorded_robot", "episodes", ["recorded_at", "robot_id"])

    op.create_table(
        "dataset_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("episodes_requested", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("episodes_requested > 0", name="ck_request_count_positive"),
        sa.CheckConstraint(
            "status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')",
            name="ck_request_status",
        ),
    )
    op.create_index("ix_dataset_requests_client_id", "dataset_requests", ["client_id"])
    op.create_index("ix_dataset_requests_status", "dataset_requests", ["status"])
    op.create_index("ix_dataset_requests_task_name", "dataset_requests", ["task_name"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("dataset_requests.id"), nullable=False),
        sa.Column("episode_pk", sa.Integer(), sa.ForeignKey("episodes.id"), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("episode_pk", name="uq_assignment_episode"),
    )
    op.create_index("ix_assignments_request_id", "assignments", ["request_id"])

    op.create_table(
        "status_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("dataset_requests.id"), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_status_events_request_id", "status_events", ["request_id"])
    op.create_index("ix_status_events_created_at", "status_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("status_events")
    op.drop_table("assignments")
    op.drop_table("dataset_requests")
    op.drop_table("episodes")
    op.drop_table("users")
