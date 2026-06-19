"""E2E API tests for /api/admin/materias endpoints.

TRIANGULATE: Tests HTTP layer via async_client with real DB.
Covers CRUD, unique codigo, deactivate.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User

from .conftest import TEST_SETTINGS


@pytest_asyncio.fixture
async def seed_admin(async_client: AsyncClient) -> dict:
    """Seed tenant + admin user."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Mat Tenant", codigo=f"MAT{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("AdminPass123!"),
            display_name="Admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()

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
            tenant_id=tenant.id, user_id=user.id, role_id=role.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur)
        await session.flush()

        data = {"tenant_id": tenant.id, "user_id": user.id}
        await session.commit()
    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def auth_token(seed_admin: dict) -> str:
    return create_access_token(
        data={"sub": str(seed_admin["user_id"]), "tenant_id": str(seed_admin["tenant_id"])}
    )


class TestMateriasCreate:
    """POST /api/admin/materias — create materia."""

    async def test_create_materia_success(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Create a materia returns 201."""
        resp = await async_client.post(
            "/api/admin/materias",
            json={"codigo": "PROG1", "nombre": "Programación I"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["codigo"] == "PROG1"
        assert body["nombre"] == "Programación I"
        assert body["estado"] == "activa"

    async def test_create_materia_duplicate_codigo(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Duplicate codigo returns 409."""
        await async_client.post(
            "/api/admin/materias",
            json={"codigo": "MATE1", "nombre": "Matemática I"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.post(
            "/api/admin/materias",
            json={"codigo": "MATE1", "nombre": "Matemática I duplicada"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 409


class TestMateriasUpdate:
    """PUT /api/admin/materias/{id} — update materia."""

    async def test_deactivate_materia(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Set estado to inactiva."""
        create_resp = await async_client.post(
            "/api/admin/materias",
            json={"codigo": "ING1", "nombre": "Inglés I"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        mid = create_resp.json()["id"]

        resp = await async_client.put(
            f"/api/admin/materias/{mid}",
            json={"estado": "inactiva"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "inactiva"

    async def test_update_materia_name(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Update name returns new name."""
        create_resp = await async_client.post(
            "/api/admin/materias",
            json={"codigo": "FIS1", "nombre": "Física I"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        mid = create_resp.json()["id"]
        resp = await async_client.put(
            f"/api/admin/materias/{mid}",
            json={"nombre": "Física I (Actualizada)"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Física I (Actualizada)"


class TestMateriasList:
    """GET /api/admin/materias — list materias."""

    async def test_list_materias(
        self, async_client: AsyncClient, auth_token: str
    ):
        """List returns created materias."""
        await async_client.post(
            "/api/admin/materias",
            json={"codigo": "A", "nombre": "Alpha"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        await async_client.post(
            "/api/admin/materias",
            json={"codigo": "B", "nombre": "Beta"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            "/api/admin/materias",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
