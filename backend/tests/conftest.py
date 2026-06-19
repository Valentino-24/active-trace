"""Shared fixtures for all tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import os

# Set env vars for Settings BEFORE any module imports it
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/t")
os.environ.setdefault("SECRET_KEY", "a-32-char-test-secret-key-for-testing-only!!")
os.environ.setdefault("ENCRYPTION_KEY", "32char-key-for-aes256-gcm-test!!")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.database import Base

# ── Test settings ────────────────────────────────────────────────────────
# DATABASE_URL_TEST env var wins (used in Docker).
# Falls back to localhost:5433 for local development.

_TEST_DB_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+asyncpg://trace:trace@localhost:5433/trace_test",
)

TEST_SETTINGS = Settings(
    _env_file=None,
    DATABASE_URL=_TEST_DB_URL,
    SECRET_KEY="a-32-char-test-secret-key-for-testing-only!!",
    ENCRYPTION_KEY="32char-key-for-aes256-gcm-test!!",
)


@pytest_asyncio.fixture
async def db_engine():
    """Create a fresh engine, create all tables, drop on teardown."""
    engine = create_async_engine(
        TEST_SETTINGS.database_url,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    db_engine,
) -> AsyncGenerator[AsyncSession, Any]:
    """Yields a session connected to the test DB."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, Any]:
    """Yields an HTTPX AsyncClient against the test app with real DB."""
    from app.main import create_app

    # Build engine + session_factory for the test DB
    engine = create_async_engine(
        TEST_SETTINGS.database_url,
        echo=False,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Build app with test settings
    app = create_app(settings=TEST_SETTINGS)
    app.state.async_session_factory = session_factory
    app.state.engine = engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Cleanup — use CASCADE to handle FK dependencies (e.g. test_item from other modules)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()
