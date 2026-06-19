"""E2E API tests for /api/admin/carreras endpoints.

TRIANGULATE: Tests HTTP layer via async_client with real DB.
Covers CRUD, unique codigo, multi-tenant isolation, auth guards.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User

from .conftest import TEST_SETTINGS

# ── Shared seed fixture ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_admin(async_client: AsyncClient) -> dict:
    """Seed tenant + admin user with estructura:gestionar permission."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    password = "AdminPass123!"
    email = f"admin-{uuid.uuid4().hex[:8]}@test.com"
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Admin Tenant", codigo=f"ADM{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
            display_name="Admin User",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # Create role + permission from scratch (no seed data in test DB)
        from datetime import date

        role = Role(tenant_id=tenant.id, nombre="Test Admin", codigo="TESTADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tenant.id, codigo="estructura:gestionar")
        session.add(perm)
        await session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp)
        await session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur)
        await session.flush()

        data = {
            "email": email,
            "password": password,
            "tenant_id": tenant.id,
            "user_id": user.id,
        }
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def seed_other_tenant(async_client: AsyncClient) -> dict:
    """Seed a different tenant with admin user."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    email = f"other-{uuid.uuid4().hex[:8]}@test.com"
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Other Tenant", codigo=f"OTH{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("OtherPass123!"),
            display_name="Other Admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        from datetime import date

        role = Role(tenant_id=tenant.id, nombre="Other Admin", codigo="OTHERADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tenant.id, codigo="estructura:gestionar")
        session.add(perm)
        await session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp)
        await session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur)
        await session.flush()

        data = {
            "email": email,
            "password": "OtherPass123!",
            "tenant_id": tenant.id,
            "user_id": user.id,
        }
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def auth_token(seed_admin: dict) -> str:
    """Generate a valid JWT for the admin user."""
    return create_access_token(
        data={
            "sub": str(seed_admin["user_id"]),
            "tenant_id": str(seed_admin["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def other_auth_token(seed_other_tenant: dict) -> str:
    """Generate a valid JWT for the other tenant admin."""
    return create_access_token(
        data={
            "sub": str(seed_other_tenant["user_id"]),
            "tenant_id": str(seed_other_tenant["tenant_id"]),
        }
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestCarrerasCreate:
    """POST /api/admin/carreras — create carrera."""

    async def test_create_carrera_success(self, async_client: AsyncClient, auth_token: str):
        """Create a carrera returns 201 with full data."""
        resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "TUP", "nombre": "Técnico Universitario en Programación"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["codigo"] == "TUP"
        assert body["nombre"] == "Técnico Universitario en Programación"
        assert body["estado"] == "activa"
        assert "id" in body
        assert "created_at" in body

    async def test_create_carrera_duplicate_codigo(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Duplicate codigo returns 409."""
        await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "LIC", "nombre": "Licenciatura"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "LIC", "nombre": "Otra Licenciatura"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 409

    async def test_create_carrera_same_codigo_different_tenant(
        self, async_client: AsyncClient, auth_token: str, other_auth_token: str
    ):
        """Same codigo in different tenant succeeds."""
        await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "COM", "nombre": "Común"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "COM", "nombre": "Común en otro"},
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 201


class TestCarrerasList:
    """GET /api/admin/carreras — list carreras."""

    async def test_list_carreras_empty(self, async_client: AsyncClient, auth_token: str):
        """Empty list returns 200 with empty items."""
        resp = await async_client.get(
            "/api/admin/carreras",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_carreras_with_data(
        self, async_client: AsyncClient, auth_token: str
    ):
        """List returns created carreras."""
        await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "TUP", "nombre": "Programación"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "TUSI", "nombre": "Sistemas"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            "/api/admin/carreras",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2


class TestCarrerasGet:
    """GET /api/admin/carreras/{id} — get by id."""

    async def test_get_carrera_success(self, async_client: AsyncClient, auth_token: str):
        """Get a carrera by ID returns 200."""
        create_resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "ING", "nombre": "Ingeniería"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        cid = create_resp.json()["id"]
        resp = await async_client.get(
            f"/api/admin/carreras/{cid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["codigo"] == "ING"

    async def test_get_carrera_not_found(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Non-existent id returns 404."""
        resp = await async_client.get(
            f"/api/admin/carreras/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    async def test_get_carrera_other_tenant_not_found(
        self, async_client: AsyncClient, auth_token: str, other_auth_token: str
    ):
        """Carrera from other tenant returns 404."""
        create_resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "PRIV", "nombre": "Privada"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        cid = create_resp.json()["id"]
        resp = await async_client.get(
            f"/api/admin/carreras/{cid}",
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 404


class TestCarrerasUpdate:
    """PUT /api/admin/carreras/{id} — update carrera."""

    async def test_update_carrera_name(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Update carrera name returns 200 with new name."""
        create_resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "UPD", "nombre": "Original"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        cid = create_resp.json()["id"]
        resp = await async_client.put(
            f"/api/admin/carreras/{cid}",
            json={"nombre": "Actualizada"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Actualizada"

    async def test_update_carrera_to_inactive(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Set estado to inactiva returns 200."""
        create_resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "INA", "nombre": "Inactivar"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        cid = create_resp.json()["id"]
        resp = await async_client.put(
            f"/api/admin/carreras/{cid}",
            json={"estado": "inactiva"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "inactiva"


class TestCarrerasDelete:
    """DELETE /api/admin/carreras/{id} — soft-delete."""

    async def test_soft_delete_carrera(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Soft-delete returns 204 and hides from list."""
        create_resp = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "DEL", "nombre": "Borrar"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        cid = create_resp.json()["id"]
        resp = await async_client.delete(
            f"/api/admin/carreras/{cid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 204

        # Verify it is gone from list
        list_resp = await async_client.get(
            "/api/admin/carreras",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert list_resp.json()["total"] == 0


class TestCarrerasAuth:
    """Auth guard tests."""

    async def test_no_auth_returns_403(
        self, async_client: AsyncClient
    ):
        """GET without token returns 403."""
        resp = await async_client.get("/api/admin/carreras")
        assert resp.status_code == 403

    async def test_without_permission_returns_403(
        self, async_client: AsyncClient, seed_admin: dict
    ):
        """User without estructura:gestionar returns 403."""
        # Create a user with NO ADMIN role
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            user = User(
                tenant_id=seed_admin["tenant_id"],
                email=f"no-perm-{uuid.uuid4().hex[:8]}@test.com",
                password_hash=hash_password("NoPerm123!"),
                display_name="No Permissions",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            await session.commit()

        token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(seed_admin["tenant_id"]),
            }
        )
        await engine.dispose()

        resp = await async_client.get(
            "/api/admin/carreras",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
