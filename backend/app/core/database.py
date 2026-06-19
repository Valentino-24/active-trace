"""Async database engine, session factory and declarative base.

Singleton engine created at application startup.
Session-per-request managed via FastAPI dependency injection.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def create_engine(settings: Settings):
    """Create the async SQLAlchemy engine.

    Args:
        settings: Application settings containing DATABASE_URL.

    Returns:
        AsyncEngine instance.
    """
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine.

    Args:
        engine: AsyncEngine instance.

    Returns:
        async_sessionmaker yielding AsyncSession.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
