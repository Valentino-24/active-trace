"""E2E tests for require_permission guard.

TRIANGULATE: Tests HTTP layer via async_client with real DB.
Covers: 200 with permiso, 403 without permiso, 401 without auth.
"""

from __future__ import annotations

from datetime import date

import pytest_asyncio
from fastapi import APIRouter, Depends
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.models.rbac import Role, Permission, RolePermission, UserRole

from .conftest import TEST_SETTINGS

# ── Test endpoint ────────────────────────────────────────────────────────────

_test_router = APIRouter()


@_test_router.get("/test-protected")
async def _protected_endpoint(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("test:acceder")),
):
    """Protected endpoint that requires 'test:acceder' permission."""
    return {"ok": True}


@_test_router.get("/test-other-perm")
async def _other_perm_endpoint(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("test:otro")),
):
    """Protected endpoint that requires 'test:otro' permission."""
    return {"ok": True}


# We'll register this router in the test itself


@pytest_asyncio.fixture
async def seed_rbac(async_client: AsyncClient) -> dict:
    """Seed tenant + user + role + permission + user_role into test DB.

    Creates a user with 'test:acceder' but NOT 'test:otro'.
    """
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Test", codigo="RP01")
        session.add(tenant)
        await session.flush()

        user = User(
            tenant_id=tenant.id,
            email="permuser@test.com",
            password_hash=hash_password("Pass1234!"),
            display_name="Perm User",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        role = Role(
            tenant_id=tenant.id,
            nombre="Test Role",
            codigo="TESTROLE",
        )
        session.add(role)
        await session.flush()

        perm = Permission(
            tenant_id=tenant.id,
            codigo="test:acceder",
        )
        session.add(perm)
        await session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp)
        await session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=user.id,
            role_id=role.id,
            desde=date(2020, 1, 1),
        )
        session.add(ur)
        await session.flush()

        data = {
            "user_id": user.id,
            "tenant_id": tenant.id,
            "email": "permuser@test.com",
            "password": "Pass1234!",
        }
        await session.commit()

    await engine.dispose()
    return data


def _get_app(client: AsyncClient):
    """Access the ASGI app wrapped by the test client's transport."""
    return client._transport.app


class TestRequirePermission:
    """TRIANGULATE: require_permission guard via HTTP."""

    async def _get_token(
        self, client: AsyncClient, email: str, password: str
    ) -> str:
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]

    async def test_with_permission_returns_200(
        self, async_client: AsyncClient, seed_rbac: dict
    ):
        """User WITH the required permission gets 200."""
        _get_app(async_client).include_router(_test_router)

        token = await self._get_token(
            async_client, seed_rbac["email"], seed_rbac["password"]
        )
        resp = await async_client.get(
            "/test-protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json() == {"ok": True}

    async def test_without_permission_returns_403(
        self, async_client: AsyncClient, seed_rbac: dict
    ):
        """User WITHOUT the required permission gets 403."""
        _get_app(async_client).include_router(_test_router)

        token = await self._get_token(
            async_client, seed_rbac["email"], seed_rbac["password"]
        )
        # This endpoint requires "test:otro" which the user doesn't have
        resp = await async_client.get(
            "/test-other-perm",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    async def test_without_auth_returns_401(
        self, async_client: AsyncClient, seed_rbac: dict
    ):
        """Unauthenticated user gets 401 (auth guard fires before permission)."""
        _get_app(async_client).include_router(_test_router)

        resp = await async_client.get("/test-protected")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
