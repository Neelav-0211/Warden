from collections.abc import Iterator

import pytest
from pytest import ExitCode, Session
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_container() -> Iterator[PostgresContainer]:
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="warden",
        password="warden",
        dbname="warden",
        driver="psycopg",
    ) as postgres:
        yield postgres


def pytest_sessionfinish(session: Session, exitstatus: int) -> None:
    if exitstatus == ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = ExitCode.OK
