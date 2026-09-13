from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from testcontainers.community.postgres import PostgresContainer


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).parents[3]
    config = Config(root / "alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.mark.integration
def test_migrations_upgrade_and_downgrade(
    pg_container: PostgresContainer,
) -> None:
    database_url = pg_container.get_connection_url()
    config = _alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) >= {
            "alembic_version",
            "jobs",
            "review_records",
            "task_steps",
            "tasks",
        }
        with engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"
                )
            )
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()
