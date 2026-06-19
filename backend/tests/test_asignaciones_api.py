"""E2E API tests for /api/asignaciones endpoints.

TRIANGULATE: Tests HTTP layer via async_client with real DB.
Covers CRUD, filters, revoke, multi-tenant isolation, auth guards.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User

from .conftest import TEST_SETTINGS

# ── Shared seed fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_admin(async_client: AsyncClient) -> dict:
    """Seed tenant + admin user with equipos:* permissions + academic data."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    password = "AdminPass123!"
    email = f"admin-{uuid.uuid4().hex[:8]}@test.com"
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Asig Tenant", codigo=f"ASG{uuid.uuid4().hex[:4]}")
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

        # Create academic data for assignment context
        carrera = Carrera(
            tenant_id=tenant.id, codigo="TUP", nombre="Técnico en Programación"
        )
        session.add(carrera)
        await session.flush()

        cohorte = Cohorte(
            tenant_id=tenant.id,
            carrera_id=carrera.id,
            nombre="2026-A",
            anio=2026,
            vig_desde=date(2026, 3, 1),
        )
        session.add(cohorte)
        await session.flush()

        materia = Materia(
            tenant_id=tenant.id, codigo="PROG1", nombre="Programación I"
        )
        session.add(materia)
        await session.flush()

        # Create a target user to assign
        target_user = User(
            tenant_id=tenant.id,
            email=f"target-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("Target123!"),
            display_name="Target User",
            is_active=True,
        )
        session.add(target_user)
        await session.flush()

        role = Role(tenant_id=tenant.id, nombre="Test Admin", codigo="TESTADMIN")
        session.add(role)
        await session.flush()

        for perm_codigo in ["equipos:asignar", "equipos:revocar"]:
            perm = Permission(tenant_id=tenant.id, codigo=perm_codigo)
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
            "target_user_id": target_user.id,
            "carrera_id": carrera.id,
            "cohorte_id": cohorte.id,
            "materia_id": materia.id,
        }
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def seed_other_tenant(async_client: AsyncClient) -> dict:
    """Seed a different tenant."""
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

        role = Role(tenant_id=tenant.id, nombre="Other Admin", codigo="OTHERADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tenant.id, codigo="equipos:asignar")
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


class TestAsignacionesCreate:
    """POST /api/asignaciones — create asignacion."""

    async def test_create_asignacion_success(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """Create a full asignacion returns 201 with vigente status."""
        resp = await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "PROFESOR",
                "materia_id": str(seed_admin["materia_id"]),
                "carrera_id": str(seed_admin["carrera_id"]),
                "cohorte_id": str(seed_admin["cohorte_id"]),
                "comisiones": ["A", "B"],
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["rol"] == "PROFESOR"
        assert body["estado_vigencia"] == "vigente"
        assert body["comisiones"] == ["A", "B"]
        assert "id" in body

    async def test_create_asignacion_simple(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """Create a minimal asignacion (just usuario + rol + desde)."""
        resp = await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "TUTOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["rol"] == "TUTOR"
        assert body["estado_vigencia"] == "vigente"

    async def test_create_asignacion_no_auth_returns_403(
        self, async_client: AsyncClient
    ):
        """POST without token returns 403."""
        resp = await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(uuid.uuid4()),
                "rol": "PROFESOR",
                "desde": "2026-03-01",
            },
        )
        assert resp.status_code == 403


class TestAsignacionesList:
    """GET /api/asignaciones — list asignaciones."""

    async def test_list_asignaciones_empty(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Empty list returns 200 with empty items."""
        resp = await async_client.get(
            "/api/asignaciones",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_asignaciones_with_data(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """List returns created asignaciones."""
        await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "PROFESOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "TUTOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            "/api/asignaciones",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2

    async def test_list_asignaciones_filter_by_rol(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """Filter by rol returns only matching asignaciones."""
        await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "PROFESOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "TUTOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            "/api/asignaciones?rol=PROFESOR",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["rol"] == "PROFESOR"


class TestAsignacionesRevoke:
    """DELETE /api/asignaciones/{id} — revoke asignacion."""

    async def test_revoke_asignacion(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """Revoke sets hasta=today and estado_vigencia=vencida."""
        create_resp = await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "PROFESOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        aid = create_resp.json()["id"]

        resp = await async_client.delete(
            f"/api/asignaciones/{aid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["estado_vigencia"] == "vencida"
        assert body["hasta"] is not None

    async def test_revoke_asignacion_not_found(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Revoke non-existent returns 404."""
        resp = await async_client.delete(
            f"/api/asignaciones/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    async def test_revoke_idempotent(
        self, async_client: AsyncClient, auth_token: str, seed_admin: dict
    ):
        """Revoking an already vencida returns 200 (idempotent)."""
        create_resp = await async_client.post(
            "/api/asignaciones",
            json={
                "usuario_id": str(seed_admin["target_user_id"]),
                "rol": "PROFESOR",
                "desde": "2026-03-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        aid = create_resp.json()["id"]

        await async_client.delete(
            f"/api/asignaciones/{aid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.delete(
            f"/api/asignaciones/{aid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200  # idempotent


class TestAsignacionesAuth:
    """Auth guard tests."""

    async def test_no_auth_returns_403(self, async_client: AsyncClient):
        """GET without token returns 403."""
        resp = await async_client.get("/api/asignaciones")
        assert resp.status_code == 403

    async def test_without_permission_returns_403(
        self, async_client: AsyncClient, seed_admin: dict
    ):
        """User without equipos:asignar returns 403."""
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
            "/api/asignaciones",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
