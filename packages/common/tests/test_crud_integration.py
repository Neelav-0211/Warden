import asyncio

import pytest
from alembic import command
from common.db import DbSettings, get_engine, session_scope
from common.db.models import Task, TaskStep, TaskStepKind
from common.types import TaskStatus
from sqlalchemy import func, select
from test_migrations_integration import _alembic_config
from testcontainers.community.postgres import PostgresContainer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_task_steps_cascade_and_updated_at_changes(
    pg_container: PostgresContainer,
) -> None:
    database_url = pg_container.get_connection_url()
    await asyncio.to_thread(command.upgrade, _alembic_config(database_url), "head")
    engine = get_engine(DbSettings(database_url=database_url))

    try:
        async with session_scope(engine) as session:
            task = Task(status=TaskStatus.PENDING, repo="acme/widgets", ref="main")
            task.steps.extend(
                [
                    TaskStep(
                        step_index=0, kind=TaskStepKind.PLAN, payload={"text": "plan"}
                    ),
                    TaskStep(
                        step_index=1,
                        kind=TaskStepKind.OBSERVATION,
                        payload={"text": "done"},
                    ),
                ]
            )
            session.add(task)

        original_updated_at = task.updated_at
        await asyncio.sleep(0.01)

        async with session_scope(engine) as session:
            stored_task = await session.get(Task, task.id)
            assert stored_task is not None
            stored_task.status = TaskStatus.RUNNING

        assert stored_task.updated_at > original_updated_at

        async with session_scope(engine) as session:
            await session.delete(stored_task)

        async with session_scope(engine) as session:
            step_count = await session.scalar(
                select(func.count()).select_from(TaskStep)
            )
            assert step_count == 0
    finally:
        await engine.dispose()
