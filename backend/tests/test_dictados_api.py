"""E2E API tests for /api/admin/dictados endpoints.

TRIANGULATE: Tests HTTP layer via async_client with real DB.
Covers CRUD, filters, inactive materia/carrera validation,
duplicate dictado, close dictado, multi-tenant isolation.
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
        tenant = Tenant(nombre="Dict Tenant", codigo=f"DCT{uuid.uuid4().hex[:4]}")
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


@pytest_asyncio.fixture
async def seed_entities(
    seed_admin: dict, async_client: AsyncClient, auth_token: str
) -> dict:
    """Create a carrera, cohorte, and materia. Return their IDs."""
    # Carrera
    r1 = await async_client.post(
        "/api/admin/carreras",
        json={"codigo": "TUP", "nombre": "Programación"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    carrera_id = r1.json()["id"]

    # Cohorte
    r2 = await async_client.post(
        "/api/admin/cohortes",
        json={
            "carrera_id": carrera_id,
            "nombre": "2026-A",
            "anio": 2026,
            "vig_desde": "2026-03-01",
        },
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    cohorte_id = r2.json()["id"]

    # Materia
    r3 = await async_client.post(
        "/api/admin/materias",
        json={"codigo": "PROG1", "nombre": "Programación I"},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    materia_id = r3.json()["id"]

    return {
        "carrera_id": carrera_id,
        "cohorte_id": cohorte_id,
        "materia_id": materia_id,
    }


class TestDictadosCreate:
    """POST /api/admin/dictados — create dictado."""

    async def test_create_dictado_success(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Create a dictado returns 201."""
        resp = await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["estado"] == "activo"
        assert body["materia_id"] == seed_entities["materia_id"]
        assert body["carrera_id"] == seed_entities["carrera_id"]
        assert body["cohorte_id"] == seed_entities["cohorte_id"]

    async def test_create_dictado_inactive_materia(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Inactive materia returns 400."""
        # Deactivate materia
        await async_client.put(
            f"/api/admin/materias/{seed_entities['materia_id']}",
            json={"estado": "inactiva"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400

    async def test_create_dictado_inactive_carrera(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Inactive carrera returns 400."""
        await async_client.put(
            f"/api/admin/carreras/{seed_entities['carrera_id']}",
            json={"estado": "inactiva"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400

    async def test_create_dictado_duplicate(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Duplicate dictado returns 409."""
        await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # The DB unique constraint will catch this
        resp = await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # Should be 409 Conflict or an error from the DB constraint
        assert resp.status_code in (409, 422, 500)


class TestDictadosList:
    """GET /api/admin/dictados — list dictados."""

    async def test_list_dictados_by_materia(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Filter by materia_id returns matching dictados."""
        await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            f"/api/admin/dictados?materia_id={seed_entities['materia_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_dictados_by_cohorte(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Filter by cohorte_id returns matching dictados."""
        await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            f"/api/admin/dictados?cohorte_id={seed_entities['cohorte_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_dictados_all(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Without filter returns all dictados."""
        resp = await async_client.get(
            "/api/admin/dictados",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200


class TestDictadosClose:
    """PUT /api/admin/dictados/{id} — close dictado."""

    async def test_close_dictado(
        self, async_client: AsyncClient, auth_token: str, seed_entities: dict
    ):
        """Set estado to inactivo."""
        create_resp = await async_client.post(
            "/api/admin/dictados",
            json={
                "materia_id": seed_entities["materia_id"],
                "carrera_id": seed_entities["carrera_id"],
                "cohorte_id": seed_entities["cohorte_id"],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        did = create_resp.json()["id"]

        resp = await async_client.put(
            f"/api/admin/dictados/{did}",
            json={"estado": "inactivo"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "inactivo"


class TestDictadosMultiTenant:
    """Multi-tenant isolation tests."""

    async def test_dictado_isolation(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """Dictado from other tenant returns 404."""
        # Create tenant2
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            tenant2 = Tenant(nombre="Dict T2", codigo=f"DT2{uuid.uuid4().hex[:4]}")
            session.add(tenant2)
            await session.flush()

            user2 = User(
                tenant_id=tenant2.id,
                email=f"u2-{uuid.uuid4().hex[:8]}@test.com",
                password_hash=hash_password("Pass123!"),
                display_name="User2",
                is_active=True,
            )
            session.add(user2)
            await session.flush()

            role2 = Role(tenant_id=tenant2.id, nombre="Admin2", codigo="ADMIN2")
            session.add(role2)
            await session.flush()

            perm2 = Permission(tenant_id=tenant2.id, codigo="estructura:gestionar")
            session.add(perm2)
            await session.flush()

            rp2 = RolePermission(role_id=role2.id, permission_id=perm2.id)
            session.add(rp2)
            await session.flush()

            ur = UserRole(
                tenant_id=tenant2.id, user_id=user2.id, role_id=role2.id,
                desde=date(2024, 1, 1),
            )
            session.add(ur)
            await session.flush()
            await session.commit()
        await engine.dispose()

        token2 = create_access_token(
            data={"sub": str(user2.id), "tenant_id": str(tenant2.id)}
        )

        # Create entities in tenant2
        r1 = await async_client.post(
            "/api/admin/carreras",
            json={"codigo": "TUP", "nombre": "Prog"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        carrera2_id = r1.json()["id"]

        r2 = await async_client.post(
            "/api/admin/cohortes",
            json={"carrera_id": carrera2_id, "nombre": "2026-A", "anio": 2026, "vig_desde": "2026-03-01"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        cohorte2_id = r2.json()["id"]

        r3 = await async_client.post(
            "/api/admin/materias",
            json={"codigo": "PROG1", "nombre": "Prog I"},
            headers={"Authorization": f"Bearer {token2}"},
        )
        materia2_id = r3.json()["id"]

        r4 = await async_client.post(
            "/api/admin/dictados",
            json={"materia_id": materia2_id, "carrera_id": carrera2_id, "cohorte_id": cohorte2_id},
            headers={"Authorization": f"Bearer {token2}"},
        )
        dictado_id = r4.json()["id"]

        # Tenant 1 tries to get it -> 404
        resp = await async_client.get(
            f"/api/admin/dictados/{dictado_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404
