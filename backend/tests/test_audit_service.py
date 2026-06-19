"""Tests for audit_service.log_action().

Strict TDD: RED → GREEN — tests define behavior before implementation.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import AuditLog, Tenant


@pytest_asyncio.fixture
async def tenant(db_session) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(nombre="Audit Test", codigo="AUDIT02")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


class TestLogAction:
    """RED→GREEN: log_action() behavior."""

    @pytest.mark.asyncio
    async def test_log_action_minimal(self, db_session, tenant):
        """log_action() with minimum required params creates an AuditLog."""
        from app.services.audit_service import log_action

        record = await log_action(
            db=db_session,
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_MINIMAL",
        )
        assert record is not None
        assert record.id is not None
        assert record.accion == "TEST_MINIMAL"
        assert record.filas_afectadas == 1  # default
        assert record.detalle is None

    @pytest.mark.asyncio
    async def test_log_action_all_params(self, db_session, tenant):
        """log_action() with all params persists correctly."""
        from app.services.audit_service import log_action

        actor_id = uuid.uuid4()
        impersonado_id = uuid.uuid4()
        record = await log_action(
            db=db_session,
            tenant_id=tenant.id,
            actor_id=actor_id,
            accion="CALIFICACIONES_IMPORTAR",
            detalle={"archivo": "notas.csv"},
            filas_afectadas=50,
            materia_id=uuid.uuid4(),
            impersonado_id=impersonado_id,
            ip="10.0.0.1",
            user_agent="TestAgent/1.0",
        )
        assert record.filas_afectadas == 50
        assert record.detalle == {"archivo": "notas.csv"}
        assert record.ip == "10.0.0.1"
        assert record.user_agent == "TestAgent/1.0"

        # Verify persistence
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.id == record.id)
        )
        loaded = result.scalar_one()
        assert loaded.actor_id == actor_id
        assert loaded.impersonado_id == impersonado_id
        assert loaded.accion == "CALIFICACIONES_IMPORTAR"

    @pytest.mark.asyncio
    async def test_log_action_with_request(self, db_session, tenant):
        """log_action() extracts IP and user-agent from request."""
        from app.services.audit_service import log_action

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get.return_value = "Browser/1.0"

        record = await log_action(
            db=db_session,
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_WITH_REQUEST",
            request=request,
        )
        assert record.ip == "192.168.1.100"
        assert record.user_agent == "Browser/1.0"
        request.headers.get.assert_called_once_with("user-agent")

    @pytest.mark.asyncio
    async def test_log_action_explicit_overrides_request(self, db_session, tenant):
        """Explicit ip/user_agent take precedence over request values."""
        from app.services.audit_service import log_action

        request = MagicMock()
        request.client.host = "192.168.1.100"
        request.headers.get.return_value = "Browser/1.0"

        record = await log_action(
            db=db_session,
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_EXPLICIT",
            ip="10.0.0.99",
            user_agent="ExplicitAgent/1.0",
            request=request,
        )
        assert record.ip == "10.0.0.99"  # explicit wins
        assert record.user_agent == "ExplicitAgent/1.0"
