"""E2E API tests for /api/admin/usuarios endpoints.

TRIANGULATE: Tests HTTP layer via async_client with real DB.
Covers CRUD, unique email, PII encryption, multi-tenant isolation, auth guards.
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

# ── Shared seed fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_admin(async_client: AsyncClient) -> dict:
    """Seed tenant + admin user with usuarios:* permissions."""
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

        role = Role(tenant_id=tenant.id, nombre="Test Admin", codigo="TESTADMIN")
        session.add(role)
        await session.flush()

        # Create both usuarios:* permissions
        for perm_codigo in ["usuarios:list", "usuarios:create", "usuarios:update"]:
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

        role = Role(tenant_id=tenant.id, nombre="Other Admin", codigo="OTHERADMIN")
        session.add(role)
        await session.flush()

        for perm_codigo in ["usuarios:list", "usuarios:create"]:
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


class TestUsuariosCreate:
    """POST /api/admin/usuarios — create user."""

    async def test_create_usuario_success(self, async_client: AsyncClient, auth_token: str):
        """Create a user returns 201 with full data (PII decrypted)."""
        resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": f"new-user-{uuid.uuid4().hex[:8]}@test.com",
                "password": "TestUser123!",
                "display_name": "New User",
                "nombre": "Juan",
                "apellidos": "Pérez",
                "dni": "12345678",
                "cuil": "20-12345678-9",
                "legajo": "LEG-001",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] is not None
        assert body["nombre"] == "Juan"
        assert body["apellidos"] == "Pérez"
        assert body["dni"] == "12345678"
        assert body["cuil"] == "20-12345678-9"
        assert body["legajo"] == "LEG-001"
        assert body["estado"] == "activo"
        assert "id" in body

    async def test_create_usuario_duplicate_email(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Duplicate email returns 409."""
        email = f"dup-{uuid.uuid4().hex[:8]}@test.com"
        await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": email,
                "password": "TestUser123!",
                "display_name": "First",
                "nombre": "First",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": email,
                "password": "TestUser123!",
                "display_name": "Second",
                "nombre": "Second",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 409

    async def test_create_usuario_same_email_different_tenant(
        self, async_client: AsyncClient, auth_token: str, other_auth_token: str
    ):
        """Same email in different tenant succeeds."""
        email = f"same-{uuid.uuid4().hex[:8]}@test.com"
        resp1 = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": email,
                "password": "TestUser123!",
                "display_name": "Tenant A",
                "nombre": "A",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp1.status_code == 201

        resp2 = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": email,
                "password": "TestUser123!",
                "display_name": "Tenant B",
                "nombre": "B",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp2.status_code == 201


class TestUsuariosList:
    """GET /api/admin/usuarios — list users."""

    async def test_list_usuarios_empty(self, async_client: AsyncClient, auth_token: str):
        """Empty list returns 200 with at least the admin user."""
        resp = await async_client.get(
            "/api/admin/usuarios",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1  # at least the admin user
        assert len(body["items"]) >= 1

    async def test_list_usuarios_no_pii_in_list(
        self, async_client: AsyncClient, auth_token: str
    ):
        """List view does NOT expose full PII (dni, cuil, cbu)."""
        await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": f"no-pii-{uuid.uuid4().hex[:8]}@test.com",
                "password": "TestUser123!",
                "display_name": "No PII",
                "nombre": "Test",
                "apellidos": "User",
                "dni": "87654321",
                "cuil": "23-87654321-9",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp = await async_client.get(
            "/api/admin/usuarios",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert "dni" not in item or item["dni"] is None
            assert "cuil" not in item or item["cuil"] is None
            assert "cbu" not in item or item["cbu"] is None

    async def test_list_usuarios_filter_by_estado(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Filter by estado=inactivo returns only inactive users."""
        resp = await async_client.get(
            "/api/admin/usuarios?estado=inactivo",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["estado"] == "inactivo"


class TestUsuariosGet:
    """GET /api/admin/usuarios/{id} — get by id."""

    async def test_get_usuario_success(self, async_client: AsyncClient, auth_token: str):
        """Get a user by ID returns 200 with full PII."""
        create_resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": f"get-me-{uuid.uuid4().hex[:8]}@test.com",
                "password": "TestUser123!",
                "display_name": "Get Me",
                "nombre": "Maria",
                "apellidos": "García",
                "dni": "11223344",
                "cuil": "27-11223344-5",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        uid = create_resp.json()["id"]

        resp = await async_client.get(
            f"/api/admin/usuarios/{uid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["nombre"] == "Maria"
        assert body["apellidos"] == "García"
        assert body["dni"] == "11223344"
        assert body["cuil"] == "27-11223344-5"

    async def test_get_usuario_not_found(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Non-existent id returns 404."""
        resp = await async_client.get(
            f"/api/admin/usuarios/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    async def test_get_usuario_other_tenant_not_found(
        self, async_client: AsyncClient, auth_token: str, other_auth_token: str
    ):
        """User from other tenant returns 404."""
        create_resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": f"private-{uuid.uuid4().hex[:8]}@test.com",
                "password": "TestUser123!",
                "display_name": "Private",
                "nombre": "Private",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        uid = create_resp.json()["id"]

        resp = await async_client.get(
            f"/api/admin/usuarios/{uid}",
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 404


class TestUsuariosUpdate:
    """PATCH /api/admin/usuarios/{id} — update user."""

    async def test_update_usuario_basic(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Update nombre/banco returns 200 with new values."""
        create_resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": f"update-me-{uuid.uuid4().hex[:8]}@test.com",
                "password": "TestUser123!",
                "display_name": "Update Me",
                "nombre": "Old",
                "apellidos": "Name",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        uid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/admin/usuarios/{uid}",
            json={"nombre": "New", "banco": "Banco Nación"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["nombre"] == "New"
        assert body["banco"] == "Banco Nación"

    async def test_update_usuario_desactivar(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Set estado to inactivo returns 200."""
        create_resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": f"deact-{uuid.uuid4().hex[:8]}@test.com",
                "password": "TestUser123!",
                "display_name": "Deactivate",
                "nombre": "Deact",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        uid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/admin/usuarios/{uid}",
            json={"estado": "inactivo"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "inactivo"

    async def test_update_usuario_email_duplicate(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Updating to an existing email returns 409."""
        email1 = f"existing-{uuid.uuid4().hex[:8]}@test.com"
        email2 = f"target-{uuid.uuid4().hex[:8]}@test.com"

        await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": email1,
                "password": "TestUser123!",
                "display_name": "Existing",
                "nombre": "Existing",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        create_resp = await async_client.post(
            "/api/admin/usuarios",
            json={
                "email": email2,
                "password": "TestUser123!",
                "display_name": "Target",
                "nombre": "Target",
                "apellidos": "User",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        uid = create_resp.json()["id"]

        resp = await async_client.patch(
            f"/api/admin/usuarios/{uid}",
            json={"email": email1},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 409


class TestUsuariosAuth:
    """Auth guard tests."""

    async def test_no_auth_returns_403(self, async_client: AsyncClient):
        """GET without token returns 403."""
        resp = await async_client.get("/api/admin/usuarios")
        assert resp.status_code == 403

    async def test_without_permission_returns_403(
        self, async_client: AsyncClient, seed_admin: dict
    ):
        """User without usuarios:* returns 403."""
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
            "/api/admin/usuarios",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
