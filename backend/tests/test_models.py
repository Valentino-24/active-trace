"""Tests for base mixins and Tenant model.

This file is the entry point for this change's TDD cycle.
Each test follows RED→GREEN: write the test, then write the code to pass it.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Tenant
from app.models.base import BaseModelMixin, SoftDeleteMixin, TenantScopedMixin


class TestMixinStructure:
    """RED→GREEN: mixin class hierarchy is correct."""

    def test_base_model_mixin_has_id_and_timestamps(self):
        """BaseModelMixin provides id, created_at, updated_at."""
        assert hasattr(BaseModelMixin, "id")
        assert hasattr(BaseModelMixin, "created_at")
        assert hasattr(BaseModelMixin, "updated_at")
        assert not hasattr(BaseModelMixin, "tenant_id")  # root only

    def test_tenant_scoped_mixin_has_tenant_id(self):
        """TenantScopedMixin adds tenant_id FK."""
        assert hasattr(TenantScopedMixin, "tenant_id")

    def test_soft_delete_mixin_has_deleted_at(self):
        """SoftDeleteMixin provides deleted_at."""
        assert hasattr(SoftDeleteMixin, "deleted_at")


class TestTenantCreate:
    """RED→GREEN: Tenant CRUD operations."""

    @pytest.mark.asyncio
    async def test_tenant_created_with_uuid(self, db_session):
        """A new Tenant gets an auto-generated UUID primary key."""
        tenant = Tenant(
            nombre="Universidad Tecnológica Nacional",
            codigo="UTN-FRC",
        )
        db_session.add(tenant)
        await db_session.flush()
        assert tenant.id is not None
        assert isinstance(tenant.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_timestamps_are_set_on_create(self, db_session):
        """created_at and updated_at are set when Tenant is persisted."""
        tenant = Tenant(nombre="Test Tenant", codigo="TS01")
        db_session.add(tenant)
        await db_session.flush()
        assert tenant.created_at is not None
        assert tenant.updated_at is not None
        assert tenant.created_at.tzinfo is not None  # timezone-aware

    @pytest.mark.asyncio
    async def test_tenant_default_estado(self, db_session):
        """New tenant defaults to 'activo'."""
        tenant = Tenant(nombre="Default Tenant", codigo="DF01")
        db_session.add(tenant)
        await db_session.flush()
        assert tenant.estado == "activo"

    @pytest.mark.asyncio
    async def test_unique_codigo_enforced(self, db_session):
        """Two tenants with the same codigo raises IntegrityError."""
        tenant_a = Tenant(nombre="Tenant A", codigo="UNIQUE")
        tenant_b = Tenant(nombre="Tenant B", codigo="UNIQUE")
        db_session.add(tenant_a)
        await db_session.flush()
        db_session.add(tenant_b)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_configuracion_is_optional(self, db_session):
        """configuracion field can be None."""
        tenant = Tenant(nombre="No Config", codigo="NOCFG")
        db_session.add(tenant)
        await db_session.flush()
        assert tenant.configuracion is None


class TestTenantSoftDelete:
    """RED→GREEN: Tenant supports soft delete."""

    @pytest.mark.asyncio
    async def test_soft_delete_sets_deleted_at(self, db_session):
        """Soft-deleting a Tenant sets deleted_at."""
        tenant = Tenant(nombre="To Delete", codigo="DEL01")
        db_session.add(tenant)
        await db_session.flush()
        # Manually soft-delete (no service layer yet, just column test)
        from datetime import UTC, datetime

        tenant.deleted_at = datetime.now(UTC)
        await db_session.flush()
        assert tenant.deleted_at is not None

    @pytest.mark.asyncio
    async def test_soft_deleted_tenant_still_exists(self, db_session):
        """Soft-deleted record is NOT removed from DB."""
        from datetime import UTC, datetime

        tenant = Tenant(nombre="Soft Delete", codigo="SD02")
        db_session.add(tenant)
        await db_session.flush()
        tid = tenant.id
        tenant.deleted_at = datetime.now(UTC)
        await db_session.flush()
        # Verify record is still queryable
        result = await db_session.execute(select(Tenant).where(Tenant.id == tid))
        assert result.scalar_one() is not None
