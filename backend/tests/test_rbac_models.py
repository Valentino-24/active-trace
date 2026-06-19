"""Tests for RBAC models: Role, Permission, RolePermission, UserRole.

RED→GREEN: Write test first, then implement the model.
"""

import uuid
from datetime import UTC, datetime, date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.base import BaseModelMixin, SoftDeleteMixin, TenantScopedMixin
from app.models.tenant import Tenant


class TestRoleStructure:
    """RED→GREEN: Role model class hierarchy and fields."""

    def test_role_inherits_tenant_scoped_mixin(self):
        """Role inherits TenantScopedMixin (has tenant_id)."""
        from app.models.rbac import Role
        assert issubclass(Role, TenantScopedMixin)

    def test_role_inherits_soft_delete_mixin(self):
        """Role inherits SoftDeleteMixin (has deleted_at)."""
        from app.models.rbac import Role
        assert issubclass(Role, SoftDeleteMixin)

    def test_role_has_codigo_field(self):
        """Role model has codigo column."""
        from app.models.rbac import Role
        assert hasattr(Role, "codigo")

    def test_role_has_nombre_field(self):
        """Role model has nombre column."""
        from app.models.rbac import Role
        assert hasattr(Role, "nombre")

    def test_role_has_descripcion_field(self):
        """Role model has descripcion nullable column."""
        from app.models.rbac import Role
        assert hasattr(Role, "descripcion")


class TestPermissionStructure:
    """RED→GREEN: Permission model structure."""

    def test_permission_inherits_tenant_scoped_mixin(self):
        """Permission inherits TenantScopedMixin."""
        from app.models.rbac import Permission
        assert issubclass(Permission, TenantScopedMixin)

    def test_permission_inherits_soft_delete_mixin(self):
        """Permission inherits SoftDeleteMixin."""
        from app.models.rbac import Permission
        assert issubclass(Permission, SoftDeleteMixin)

    def test_permission_has_codigo_field(self):
        """Permission model has codigo column."""
        from app.models.rbac import Permission
        assert hasattr(Permission, "codigo")

    def test_permission_has_descripcion_field(self):
        """Permission model has descripcion nullable column."""
        from app.models.rbac import Permission
        assert hasattr(Permission, "descripcion")


class TestRolePermissionStructure:
    """RED→GREEN: RolePermission is a pure relationship table."""

    def test_role_permission_inherits_base_model_mixin(self):
        """RolePermission inherits BaseModelMixin (id + timestamps)."""
        from app.models.rbac import RolePermission
        assert issubclass(RolePermission, BaseModelMixin)

    def test_role_permission_does_not_inherit_tenant_scoped(self):
        """RolePermission does NOT have tenant_id (pure relationship)."""
        from app.models.rbac import RolePermission
        assert not issubclass(RolePermission, TenantScopedMixin)
        assert not hasattr(RolePermission, "tenant_id")

    def test_role_permission_does_not_inherit_soft_delete(self):
        """RolePermission does NOT have deleted_at (pure relationship)."""
        from app.models.rbac import RolePermission
        assert not issubclass(RolePermission, SoftDeleteMixin)
        assert not hasattr(RolePermission, "deleted_at")

    def test_role_permission_has_role_id(self):
        """RolePermission has role_id FK."""
        from app.models.rbac import RolePermission
        assert hasattr(RolePermission, "role_id")

    def test_role_permission_has_permission_id(self):
        """RolePermission has permission_id FK."""
        from app.models.rbac import RolePermission
        assert hasattr(RolePermission, "permission_id")


class TestUserRoleStructure:
    """RED→GREEN: UserRole model structure."""

    def test_user_role_inherits_tenant_scoped_mixin(self):
        """UserRole inherits TenantScopedMixin."""
        from app.models.rbac import UserRole
        assert issubclass(UserRole, TenantScopedMixin)

    def test_user_role_inherits_soft_delete_mixin(self):
        """UserRole inherits SoftDeleteMixin."""
        from app.models.rbac import UserRole
        assert issubclass(UserRole, SoftDeleteMixin)

    def test_user_role_has_user_id(self):
        """UserRole has user_id FK."""
        from app.models.rbac import UserRole
        assert hasattr(UserRole, "user_id")

    def test_user_role_has_role_id(self):
        """UserRole has role_id FK."""
        from app.models.rbac import UserRole
        assert hasattr(UserRole, "role_id")

    def test_user_role_has_desde_field(self):
        """UserRole has desde (date) column."""
        from app.models.rbac import UserRole
        assert hasattr(UserRole, "desde")

    def test_user_role_has_hasta_field(self):
        """UserRole has hasta (date) nullable column."""
        from app.models.rbac import UserRole
        assert hasattr(UserRole, "hasta")


class TestRoleCreate:
    """RED→GREEN: Role persistence and constraints."""

    @pytest.mark.asyncio
    async def test_role_created_with_uuid(self, db_session):
        """Role gets an auto-generated UUID primary key."""
        from app.models.rbac import Role
        tenant = Tenant(nombre="Test", codigo="RL01")
        db_session.add(tenant)
        await db_session.flush()

        role = Role(
            tenant_id=tenant.id,
            nombre="Profesor",
            codigo="PROFESOR",
            descripcion="Docente a cargo de comisiones",
        )
        db_session.add(role)
        await db_session.flush()
        assert role.id is not None
        assert isinstance(role.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_role_timestamps_set(self, db_session):
        """created_at and updated_at are populated on persist."""
        from app.models.rbac import Role
        tenant = Tenant(nombre="Test", codigo="RL02")
        db_session.add(tenant)
        await db_session.flush()

        role = Role(
            tenant_id=tenant.id,
            nombre="Alumno",
            codigo="ALUMNO",
        )
        db_session.add(role)
        await db_session.flush()
        assert role.created_at is not None
        assert role.updated_at is not None

    @pytest.mark.asyncio
    async def test_unique_codigo_per_tenant(self, db_session):
        """Two roles with same codigo in same tenant raises IntegrityError."""
        from app.models.rbac import Role
        tenant = Tenant(nombre="Test", codigo="RL03")
        db_session.add(tenant)
        await db_session.flush()

        role_a = Role(
            tenant_id=tenant.id, nombre="Admin", codigo="ADMIN"
        )
        role_b = Role(
            tenant_id=tenant.id, nombre="Admin Dupe", codigo="ADMIN"
        )
        db_session.add(role_a)
        await db_session.flush()
        db_session.add(role_b)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_same_codigo_different_tenants_allowed(self, db_session):
        """Two roles with same codigo in DIFFERENT tenants is OK."""
        from app.models.rbac import Role
        t1 = Tenant(nombre="T1", codigo="RL04A")
        t2 = Tenant(nombre="T2", codigo="RL04B")
        db_session.add(t1)
        db_session.add(t2)
        await db_session.flush()

        role_a = Role(
            tenant_id=t1.id, nombre="Admin", codigo="ADMIN"
        )
        role_b = Role(
            tenant_id=t2.id, nombre="Admin", codigo="ADMIN"
        )
        db_session.add(role_a)
        db_session.add(role_b)
        await db_session.flush()
        assert role_a.id is not None
        assert role_b.id is not None

    @pytest.mark.asyncio
    async def test_descripcion_nullable(self, db_session):
        """descripcion can be None."""
        from app.models.rbac import Role
        tenant = Tenant(nombre="Test", codigo="RL05")
        db_session.add(tenant)
        await db_session.flush()

        role = Role(
            tenant_id=tenant.id, nombre="No Desc", codigo="NODESC"
        )
        db_session.add(role)
        await db_session.flush()
        assert role.descripcion is None


class TestPermissionCreate:
    """RED→GREEN: Permission persistence and constraints."""

    @pytest.mark.asyncio
    async def test_permission_created_with_uuid(self, db_session):
        """Permission gets an auto-generated UUID primary key."""
        from app.models.rbac import Permission
        tenant = Tenant(nombre="Test", codigo="PM01")
        db_session.add(tenant)
        await db_session.flush()

        perm = Permission(
            tenant_id=tenant.id,
            codigo="calificaciones:importar",
            descripcion="Importar calificaciones",
        )
        db_session.add(perm)
        await db_session.flush()
        assert perm.id is not None
        assert isinstance(perm.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_unique_codigo_per_tenant_permission(self, db_session):
        """Two permissions with same codigo in same tenant raises IntegrityError."""
        from app.models.rbac import Permission
        tenant = Tenant(nombre="Test", codigo="PM02")
        db_session.add(tenant)
        await db_session.flush()

        perm_a = Permission(
            tenant_id=tenant.id, codigo="calificaciones:importar"
        )
        perm_b = Permission(
            tenant_id=tenant.id, codigo="calificaciones:importar"
        )
        db_session.add(perm_a)
        await db_session.flush()
        db_session.add(perm_b)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_permission_descripcion_nullable(self, db_session):
        """Permission descripcion can be None."""
        from app.models.rbac import Permission
        tenant = Tenant(nombre="Test", codigo="PM03")
        db_session.add(tenant)
        await db_session.flush()

        perm = Permission(
            tenant_id=tenant.id, codigo="auditoria:ver"
        )
        db_session.add(perm)
        await db_session.flush()
        assert perm.descripcion is None


class TestRolePermissionCreate:
    """RED→GREEN: RolePermission relationships."""

    @pytest.mark.asyncio
    async def test_create_role_permission(self, db_session):
        """Create a role-permission association."""
        from app.models.rbac import Role, Permission, RolePermission
        tenant = Tenant(nombre="Test", codigo="RP01")
        db_session.add(tenant)
        await db_session.flush()

        role = Role(
            tenant_id=tenant.id, nombre="Admin", codigo="ADMIN"
        )
        perm = Permission(
            tenant_id=tenant.id, codigo="usuarios:gestionar"
        )
        db_session.add(role)
        db_session.add(perm)
        await db_session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        db_session.add(rp)
        await db_session.flush()
        assert rp.id is not None
        assert isinstance(rp.id, uuid.UUID)
        assert rp.role_id == role.id
        assert rp.permission_id == perm.id

    @pytest.mark.asyncio
    async def test_unique_role_permission(self, db_session):
        """Duplicate role_id + permission_id raises IntegrityError."""
        from app.models.rbac import Role, Permission, RolePermission
        tenant = Tenant(nombre="Test", codigo="RP02")
        db_session.add(tenant)
        await db_session.flush()

        role = Role(
            tenant_id=tenant.id, nombre="Admin", codigo="ADMIN2"
        )
        perm = Permission(
            tenant_id=tenant.id, codigo="tenant:configurar"
        )
        db_session.add(role)
        db_session.add(perm)
        await db_session.flush()

        rp1 = RolePermission(role_id=role.id, permission_id=perm.id)
        db_session.add(rp1)
        await db_session.flush()
        rp2 = RolePermission(role_id=role.id, permission_id=perm.id)
        db_session.add(rp2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_role_permission_has_timestamps(self, db_session):
        """RolePermission has created_at and updated_at."""
        from app.models.rbac import Role, Permission, RolePermission
        tenant = Tenant(nombre="Test", codigo="RP03")
        db_session.add(tenant)
        await db_session.flush()

        role = Role(
            tenant_id=tenant.id, nombre="Admin", codigo="ADMIN3"
        )
        perm = Permission(
            tenant_id=tenant.id, codigo="auditoria:ver"
        )
        db_session.add(role)
        db_session.add(perm)
        await db_session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        db_session.add(rp)
        await db_session.flush()
        assert rp.created_at is not None
        assert rp.updated_at is not None


class TestUserRoleCreate:
    """RED→GREEN: UserRole persistence and constraints."""

    @pytest.mark.asyncio
    async def test_create_user_role(self, db_session):
        """Create a user-role assignment with dates."""
        from app.models.rbac import Role, UserRole
        from app.models.user import User
        tenant = Tenant(nombre="Test", codigo="UR01")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="profesor@test.com",
            password_hash="hash",
            display_name="Prof",
        )
        role = Role(
            tenant_id=tenant.id, nombre="Profesor", codigo="PROFESOR"
        )
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2026, 1, 1),
        )
        db_session.add(ur)
        await db_session.flush()
        assert ur.id is not None
        assert isinstance(ur.id, uuid.UUID)
        assert ur.desde == date(2026, 1, 1)
        assert ur.hasta is None

    @pytest.mark.asyncio
    async def test_user_role_with_hasta(self, db_session):
        """UserRole can have hasta date (end of validity)."""
        from app.models.rbac import Role, UserRole
        from app.models.user import User
        tenant = Tenant(nombre="Test", codigo="UR02")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="tutor@test.com",
            password_hash="hash",
            display_name="Tutor",
        )
        role = Role(
            tenant_id=tenant.id, nombre="Tutor", codigo="TUTOR"
        )
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2025, 3, 1),
            hasta=date(2025, 12, 31),
        )
        db_session.add(ur)
        await db_session.flush()
        assert ur.hasta == date(2025, 12, 31)

    @pytest.mark.asyncio
    async def test_unique_user_role_desde(self, db_session):
        """Duplicate user_id + role_id + desde raises IntegrityError."""
        from app.models.rbac import Role, UserRole
        from app.models.user import User
        tenant = Tenant(nombre="Test", codigo="UR03")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="dupe@test.com",
            password_hash="hash",
            display_name="Dupe",
        )
        role = Role(
            tenant_id=tenant.id, nombre="Admin", codigo="ADMIN"
        )
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        ur1 = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2026, 1, 1),
        )
        db_session.add(ur1)
        await db_session.flush()
        ur2 = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2026, 1, 1),
        )
        db_session.add(ur2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_user_role_soft_delete(self, db_session):
        """UserRole supports soft delete."""
        from app.models.rbac import Role, UserRole
        from app.models.user import User
        tenant = Tenant(nombre="Test", codigo="UR04")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="sdel@test.com",
            password_hash="hash",
            display_name="SDel",
        )
        role = Role(
            tenant_id=tenant.id, nombre="Admin", codigo="ADMIN2"
        )
        db_session.add(user)
        db_session.add(role)
        await db_session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2026, 1, 1),
        )
        db_session.add(ur)
        await db_session.flush()
        uid = ur.id
        ur.deleted_at = datetime.now(UTC)
        await db_session.flush()

        result = await db_session.execute(
            select(UserRole).where(UserRole.id == uid)
        )
        persisted = result.scalar_one()
        assert persisted.deleted_at is not None
