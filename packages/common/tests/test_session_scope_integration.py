import asyncio

import pytest
from alembic import command
from common.db import DbSettings, get_engine, session_scope
from common.db.models import Job
from common.types import JobStatus
from sqlalchemy import func, select
from test_migrations_integration import _alembic_config
from testcontainers.community.postgres import PostgresContainer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_scope_commits_and_rolls_back(
    pg_container: PostgresContainer,
) -> None:
    database_url = pg_container.get_connection_url()
    await asyncio.to_thread(command.upgrade, _alembic_config(database_url), "head")
    engine = get_engine(DbSettings(database_url=database_url))

    try:
        async with session_scope(engine) as session:
            session.add(Job(queue_name="reviews", status=JobStatus.QUEUED))

        with pytest.raises(RuntimeError, match="worker failed"):
            async with session_scope(engine) as session:
                session.add(Job(queue_name="coding", status=JobStatus.QUEUED))
                raise RuntimeError("worker failed")

        async with session_scope(engine) as session:
            job_count = await session.scalar(select(func.count()).select_from(Job))
            assert job_count == 1
    finally:
        await engine.dispose()
