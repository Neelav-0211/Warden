import pytest
from common.db.models import Job, ReviewRecord, Task, TaskStep
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID


@pytest.mark.unit
@pytest.mark.parametrize(
    ("model", "expected_columns"),
    [
        (
            Task,
            {"id", "status", "repo", "ref", "created_at", "updated_at"},
        ),
        (
            TaskStep,
            {"id", "task_id", "step_index", "kind", "payload", "created_at"},
        ),
        (
            ReviewRecord,
            {"id", "pr_number", "repo", "status", "summary", "created_at"},
        ),
        (
            Job,
            {"id", "queue_name", "status", "attempts", "last_error"},
        ),
    ],
)
def test_models_declare_expected_columns(
    model: type[Task | TaskStep | ReviewRecord | Job],
    expected_columns: set[str],
) -> None:
    assert set(model.__table__.columns.keys()) == expected_columns


@pytest.mark.unit
def test_models_use_expected_database_types() -> None:
    assert isinstance(Task.__table__.c.id.type, UUID)
    assert isinstance(Task.__table__.c.status.type, Enum)
    assert isinstance(Task.__table__.c.repo.type, String)
    assert isinstance(TaskStep.__table__.c.task_id.type, UUID)
    assert isinstance(TaskStep.__table__.c.step_index.type, Integer)
    assert isinstance(TaskStep.__table__.c.kind.type, Enum)
    assert isinstance(TaskStep.__table__.c.payload.type, JSONB)
    assert isinstance(ReviewRecord.__table__.c.pr_number.type, Integer)
    assert isinstance(ReviewRecord.__table__.c.summary.type, Text)
    assert isinstance(Job.__table__.c.last_error.type, Text)


@pytest.mark.unit
def test_task_step_foreign_key_cascades_on_delete() -> None:
    foreign_key = next(iter(TaskStep.__table__.c.task_id.foreign_keys))

    assert isinstance(foreign_key, ForeignKey)
    assert foreign_key.target_fullname == "tasks.id"
    assert foreign_key.ondelete == "CASCADE"
