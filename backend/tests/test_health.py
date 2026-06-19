"""Tests for GET /health endpoint."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_db
from app.main import create_app

pytestmark = pytest.mark.asyncio


async def test_health_returns_200(async_client):
    """GET /health returns 200 with status field."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "database" in body


async def test_health_db_down():
    """When DB is down, GET /health returns 200 with database: down.

    The endpoint must NOT crash when the database is unreachable.
    It reports degraded status (database: down) but responds 200 OK.
    """
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://trace:trace@localhost:5433/trace_test",
        SECRET_KEY="a-32-char-test-secret-key-for-testing-only!!",
        ENCRYPTION_KEY="a-32-char-test-encryption-key-for-testing!!",
    )
    app = create_app(settings=settings)

    # Override get_db to inject a session whose execute() call fails
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = ConnectionRefusedError("DB unavailable")

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "down"

    # Clean up overrides so they don't leak to other tests
    app.dependency_overrides.clear()
