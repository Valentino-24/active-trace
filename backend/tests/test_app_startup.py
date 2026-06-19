"""Tests for app startup — app factory creates without error."""

from app.core.config import Settings
from app.main import create_app


def test_create_app_returns_app():
    """create_app() returns a FastAPI application without error."""
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://trace:trace@localhost:5433/trace_test",
        SECRET_KEY="a-32-char-test-secret-key-for-testing-only!!",
        ENCRYPTION_KEY="a-32-char-test-encryption-key-for-testing!!",
    )
    app = create_app(settings=settings)
    assert app.title == "activia-trace"
    assert app.version == "0.1.0"
