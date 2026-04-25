"""
DAI Server — Async Database Session
=====================================

Provides the async SQLAlchemy engine and session factory.
Uses environment variable ``DAI_DATABASE_URL`` for connection string.
"""


import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from dai_server.db.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the async engine, creating it if needed."""
    global _engine
    if _engine is None:
        database_url = os.environ.get(
            "DAI_DATABASE_URL",
            "postgresql+asyncpg://dai:dai@localhost:5432/dai",
        )
        _engine = create_async_engine(
            database_url,
            echo=os.environ.get("DAI_LOG_LEVEL", "INFO").upper() == "DEBUG",
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory, creating it if needed."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that provides an AsyncSession per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables defined in the ORM models. Called at server startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_engine() -> None:
    """Dispose of the engine connection pool. Called at server shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
