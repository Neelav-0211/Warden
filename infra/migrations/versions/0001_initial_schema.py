"""Create the initial Warden persistence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

task_status = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
    name="task_status",
    create_type=False,
)
job_status = postgresql.ENUM(
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    name="job_status",
    create_type=False,
)
task_step_kind = postgresql.ENUM(
    "plan",
    "tool_call",
    "observation",
    name="task_step_kind",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    task_status.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)
    task_step_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column("repo", sa.String(length=512), nullable=False),
        sa.Column("ref", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "review_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("repo", sa.String(length=512), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("queue_name", sa.String(length=255), nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("kind", task_step_kind, nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id", "step_index", name="uq_task_steps_task_step_index"
        ),
    )


def downgrade() -> None:
    op.drop_table("task_steps")
    op.drop_table("jobs")
    op.drop_table("review_records")
    op.drop_table("tasks")
    task_step_kind.drop(op.get_bind(), checkfirst=True)
    job_status.drop(op.get_bind(), checkfirst=True)
    task_status.drop(op.get_bind(), checkfirst=True)
