"""Tests for FastAPI dependency injection — get_db session lifecycle."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dependencies import get_db

pytestmark = pytest.mark.asyncio


async def test_get_db_closes_session_on_exception():
    """Session.close() is called when an exception escapes the get_db scope.

    This verifies the finally block in get_db — even if the request handler
    raises, the session must be closed to avoid connection leaks to the pool.
    """
    # Arrange: a mock session + factory
    mock_session = AsyncMock()
    mock_factory = MagicMock(return_value=mock_session)

    request = MagicMock()
    request.app.state.async_session_factory = mock_factory

    # Act: advance the generator to the yield point
    agen = get_db(request)
    session = await agen.__anext__()

    assert session is mock_session
    mock_session.close.assert_not_called()

    # Throw an exception into the generator — the finally block should run
    with pytest.raises(RuntimeError, match="test crash"):
        await agen.athrow(RuntimeError("test crash"))

    # Assert: close() was awaited exactly once
    mock_session.close.assert_awaited_once()
