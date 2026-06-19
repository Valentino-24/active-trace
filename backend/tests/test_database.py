"""Tests for async database connection."""

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_db_session_select_one(db_session):
    """An async session can execute SELECT 1 and get a result."""
    result = await db_session.execute(text("SELECT 1"))
    val = result.scalar_one()
    assert val == 1


@pytest.mark.asyncio
async def test_db_connection_up(db_engine):
    """Engine connects to the database and executes a simple query."""
    async with db_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 AS num"))
        row = result.one()
        assert row.num == 1
