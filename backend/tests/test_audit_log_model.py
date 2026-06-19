"""Tests for AuditLog model — append-only entity.

Strict TDD: RED → GREEN — tests reference AuditLog before its implementation.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models import AuditLog, Tenant
from app.repositories.audit_log_repository import AuditLogRepository


@pytest_asyncio.fixture
async def tenant(db_session) -> Tenant:
    """Create a test tenant for audit log tests."""
    tenant = Tenant(nombre="Audit Test", codigo="AUDIT01")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


class TestAuditLogCreate:
    """RED→GREEN: AuditLog model creation."""

    @pytest.mark.asyncio
    async def test_audit_log_created_with_uuid(self, db_session, tenant):
        """A new AuditLog gets an auto-generated UUID primary key."""
        record = AuditLog(
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_ACTION",
            filas_afectadas=1,
        )
        db_session.add(record)
        await db_session.flush()
        assert record.id is not None
        assert isinstance(record.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_audit_log_has_fecha_hora(self, db_session, tenant):
        """fecha_hora is set automatically on creation."""
        record = AuditLog(
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_ACTION",
        )
        db_session.add(record)
        await db_session.flush()
        assert record.fecha_hora is not None

    @pytest.mark.asyncio
    async def test_audit_log_all_fields(self, db_session, tenant):
        """All AuditLog fields can be set and persisted."""
        actor_id = uuid.uuid4()
        impersonado_id = uuid.uuid4()
        record = AuditLog(
            tenant_id=tenant.id,
            actor_id=actor_id,
            impersonado_id=impersonado_id,
            accion="CALIFICACIONES_IMPORTAR",
            detalle={"archivo": "notas.csv", "cantidad": 50},
            filas_afectadas=50,
            ip="192.168.1.1",
            user_agent="Mozilla/5.0 Test",
        )
        db_session.add(record)
        await db_session.flush()

        # Re-read to verify persistence
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.id == record.id)
        )
        loaded = result.scalar_one()

        assert loaded.tenant_id == tenant.id
        assert loaded.actor_id == actor_id
        assert loaded.impersonado_id == impersonado_id
        assert loaded.accion == "CALIFICACIONES_IMPORTAR"
        assert loaded.detalle == {"archivo": "notas.csv", "cantidad": 50}
        assert loaded.filas_afectadas == 50
        assert loaded.ip == "192.168.1.1"
        assert loaded.user_agent == "Mozilla/5.0 Test"

    @pytest.mark.asyncio
    async def test_audit_log_default_filas_afectadas(self, db_session, tenant):
        """filas_afectadas defaults to 1."""
        record = AuditLog(
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_ACTION",
        )
        db_session.add(record)
        await db_session.flush()
        assert record.filas_afectadas == 1

    @pytest.mark.asyncio
    async def test_audit_log_nullable_fields(self, db_session, tenant):
        """impersonado_id, materia_id, ip, user_agent, detalle can be None."""
        record = AuditLog(
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_ACTION",
        )
        db_session.add(record)
        await db_session.flush()
        assert record.impersonado_id is None
        assert record.materia_id is None
        assert record.ip is None
        assert record.user_agent is None
        assert record.detalle is None


class TestAuditLogAppendOnly:
    """RED→GREEN: AuditLog does NOT support update or delete."""

    @pytest.mark.asyncio
    async def test_audit_log_has_no_deleted_at(self, db_session, tenant):
        """AuditLog does NOT have soft-delete support."""
        record = AuditLog(
            tenant_id=tenant.id,
            actor_id=uuid.uuid4(),
            accion="TEST_ACTION",
        )
        db_session.add(record)
        await db_session.flush()
        assert not hasattr(record, "deleted_at")

    @pytest.mark.asyncio
    async def test_repository_blocks_update(self, db_session, tenant):
        """AuditLogRepository.update() raises RuntimeError."""
        repo = AuditLogRepository(session=db_session, tenant_id=tenant.id)
        with pytest.raises(RuntimeError, match="does not support update"):
            await repo.update(filas_afectadas=999)

    @pytest.mark.asyncio
    async def test_repository_blocks_delete(self, db_session, tenant):
        """AuditLogRepository.soft_delete() raises RuntimeError."""
        repo = AuditLogRepository(session=db_session, tenant_id=tenant.id)
        with pytest.raises(RuntimeError, match="does not support delete"):
            await repo.soft_delete(id=uuid.uuid4())
