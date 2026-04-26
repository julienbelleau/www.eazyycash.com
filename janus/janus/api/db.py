"""Async SQLAlchemy session factory shared across the API.

Single engine per process; FastAPI dependency `get_session` yields a session
per request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from janus.config.settings import get_settings


@lru_cache(maxsize=1)
def _engine() -> object:
    settings = get_settings()
    return create_async_engine(
        settings.database.async_dsn,
        future=True,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
    )


@lru_cache(maxsize=1)
def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(_engine(), expire_on_commit=False)  # type: ignore[arg-type]


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _sessionmaker()() as session:
        try:
            yield session
        finally:
            await session.close()
