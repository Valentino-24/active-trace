"""Tests for get_user_permissions — permission resolution engine.

RED→GREEN: Write test first, then implement get_user_permissions.
"""

import uuid
from datetime import date, datetime, UTC

import pytest
from sqlalchemy import select

from app.models import User, Role, Permission, RolePermission, UserRole
from app.models.tenant import Tenant


@pytest.mark.asyncio
async def test_no_roles_returns_empty_set(db_session):
    """User with no roles gets an empty set of permissions."""
    tenant = Tenant(nombre="Test", codigo="PRM00")
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="noroles@test.com",
        password_hash="hash",
        display_name="No Roles",
    )
    db_session.add(user)
    await db_session.flush()

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(db_session, user)
    assert isinstance(perms, set)
    assert len(perms) == 0


@pytest.mark.asyncio
async def test_single_role_permissions(db_session):
    """User with one role gets that role's permissions."""
    tenant = Tenant(nombre="Test", codigo="PRM01")
    db_session.add(tenant)
    await db_session.flush()

    role = Role(
        tenant_id=tenant.id,
        nombre="Alumno",
        codigo="ALUMNO",
    )
    perm_a = Permission(
        tenant_id=tenant.id,
        codigo="estado:ver_propio",
    )
    perm_b = Permission(
        tenant_id=tenant.id,
        codigo="evaluacion:reservar",
    )
    db_session.add(role)
    db_session.add(perm_a)
    db_session.add(perm_b)
    await db_session.flush()

    rp_a = RolePermission(role_id=role.id, permission_id=perm_a.id)
    rp_b = RolePermission(role_id=role.id, permission_id=perm_b.id)
    db_session.add(rp_a)
    db_session.add(rp_b)
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="alumno@test.com",
        password_hash="hash",
        display_name="Alumno",
    )
    db_session.add(user)
    await db_session.flush()

    ur = UserRole(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role.id,
        desde=date(2020, 1, 1),
    )
    db_session.add(ur)
    await db_session.flush()

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(db_session, user)
    assert perms == {"estado:ver_propio", "evaluacion:reservar"}


@pytest.mark.asyncio
async def test_union_of_roles(db_session):
    """User with two roles gets permissions from both (union)."""
    tenant = Tenant(nombre="Test", codigo="PRM02")
    db_session.add(tenant)
    await db_session.flush()

    role_a = Role(
        tenant_id=tenant.id,
        nombre="Alumno",
        codigo="ALUMNO",
    )
    role_b = Role(
        tenant_id=tenant.id,
        nombre="Tutor",
        codigo="TUTOR",
    )
    perm_a = Permission(
        tenant_id=tenant.id, codigo="estado:ver_propio"
    )
    perm_b = Permission(
        tenant_id=tenant.id, codigo="evaluacion:reservar"
    )
    perm_c = Permission(
        tenant_id=tenant.id, codigo="avisos:confirmar"
    )
    db_session.add(role_a)
    db_session.add(role_b)
    db_session.add(perm_a)
    db_session.add(perm_b)
    db_session.add(perm_c)
    await db_session.flush()

    # Role A gets perm_a + perm_b
    db_session.add(RolePermission(role_id=role_a.id, permission_id=perm_a.id))
    db_session.add(RolePermission(role_id=role_a.id, permission_id=perm_b.id))
    # Role B gets perm_c
    db_session.add(RolePermission(role_id=role_b.id, permission_id=perm_c.id))
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="multirol@test.com",
        password_hash="hash",
        display_name="Multirol",
    )
    db_session.add(user)
    await db_session.flush()

    # Assign both roles
    db_session.add(UserRole(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role_a.id,
        desde=date(2020, 1, 1),
    ))
    db_session.add(UserRole(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role_b.id,
        desde=date(2020, 1, 1),
    ))
    await db_session.flush()

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(db_session, user)
    assert perms == {"estado:ver_propio", "evaluacion:reservar", "avisos:confirmar"}


@pytest.mark.asyncio
async def test_active_role_includes_permissions(db_session):
    """Active role (desde in past, hasta NULL) includes permissions."""
    tenant = Tenant(nombre="Test", codigo="PRM03")
    db_session.add(tenant)
    await db_session.flush()

    role = Role(
        tenant_id=tenant.id, nombre="Profesor", codigo="PROFESOR"
    )
    perm = Permission(
        tenant_id=tenant.id, codigo="calificaciones:importar"
    )
    db_session.add(role)
    db_session.add(perm)
    await db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="activo@test.com",
        password_hash="hash",
        display_name="Activo",
    )
    db_session.add(user)
    await db_session.flush()

    # desde in the past, hasta NULL
    db_session.add(UserRole(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role.id,
        desde=date(2020, 1, 1),
        hasta=None,
    ))
    await db_session.flush()

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(db_session, user)
    assert "calificaciones:importar" in perms


@pytest.mark.asyncio
async def test_expired_role_excludes_permissions(db_session):
    """User with expired role (hasta in the past) does NOT get permissions."""
    tenant = Tenant(nombre="Test", codigo="PRM04")
    db_session.add(tenant)
    await db_session.flush()

    role = Role(
        tenant_id=tenant.id, nombre="Profesor", codigo="PROFESOR"
    )
    perm = Permission(
        tenant_id=tenant.id, codigo="calificaciones:importar"
    )
    db_session.add(role)
    db_session.add(perm)
    await db_session.flush()
    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="vencido@test.com",
        password_hash="hash",
        display_name="Vencido",
    )
    db_session.add(user)
    await db_session.flush()

    # hasta in the past → expired
    db_session.add(UserRole(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role.id,
        desde=date(2020, 1, 1),
        hasta=date(2020, 12, 31),
    ))
    await db_session.flush()

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(db_session, user)
    assert "calificaciones:importar" not in perms
    assert len(perms) == 0


@pytest.mark.asyncio
async def test_soft_deleted_user_role_excluded(db_session):
    """Soft-deleted UserRole should not contribute permissions."""
    tenant = Tenant(nombre="Test", codigo="PRM05")
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
    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="softdel@test.com",
        password_hash="hash",
        display_name="SoftDel",
    )
    db_session.add(user)
    await db_session.flush()

    ur = UserRole(
        tenant_id=tenant.id,
        user_id=user.id,
        role_id=role.id,
        desde=date(2020, 1, 1),
    )
    db_session.add(ur)
    await db_session.flush()

    # Soft-delete the user_role
    ur.deleted_at = datetime.now(UTC)
    await db_session.flush()

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(db_session, user)
    assert "usuarios:gestionar" not in perms
    assert len(perms) == 0
