from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DbSettings(BaseModel):
    database_url: str
    database_echo: bool = False


def get_engine(settings: DbSettings) -> AsyncEngine:
    database_url = settings.database_url
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace(
            "postgresql+psycopg://", "postgresql+asyncpg://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return create_async_engine(database_url, echo=settings.database_echo)


@asynccontextmanager
async def session_scope(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
