"""E2E tests for get_current_user with impersonation.

Strict TDD: RED → GREEN — tests define behavior before get_current_user
handles impersonation.
"""

from __future__ import annotations

from datetime import date

import pytest_asyncio
from fastapi import APIRouter, Depends
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.dependencies import get_current_user, get_db
from app.core.security import create_impersonation_token, create_access_token, hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.models.rbac import Role, Permission, RolePermission, UserRole

from .conftest import TEST_SETTINGS

# ── Test endpoint ────────────────────────────────────────────────────────────

_test_router = APIRouter()


@_test_router.get("/test-whoami")
async def _whoami(
    current_user: User = Depends(get_current_user),
):
    """Returns user identity info including impersonation state."""
    return {
        "user_id": str(current_user.id),
        "is_impersonating": current_user.is_impersonating,
    }


@_test_router.get("/test-permissions")
async def _permissions(
    current_user: User = Depends(get_current_user),
):
    """Returns user's effective permissions."""
    return {
        "user_id": str(current_user.id),
        "is_impersonating": current_user.is_impersonating,
        "permissions": sorted(current_user.permissions),
    }


@pytest_asyncio.fixture
async def seed_impersonation(async_client: AsyncClient) -> dict:
    """Seed: tenant, admin user (with impersonacion:usar), target user (no perms)."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Imp Test", codigo="IMP01")
        session.add(tenant)
        await session.flush()
        tid = tenant.id

        # Admin user — has impersonacion:usar
        admin = User(
            tenant_id=tid,
            email="admin@test.com",
            password_hash=hash_password("AdminPass1!"),
            display_name="Admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        # Target user — no special permissions
        target = User(
            tenant_id=tid,
            email="target@test.com",
            password_hash=hash_password("TargetPass1!"),
            display_name="Target",
            is_active=True,
        )
        session.add(target)
        await session.flush()

        # Create role + permission for impersonacion:usar
        role = Role(tenant_id=tid, nombre="Admin Role", codigo="ADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tid, codigo="impersonacion:usar")
        session.add(perm)
        await session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp)
        await session.flush()

        ur = UserRole(
            tenant_id=tid,
            user_id=admin.id,
            role_id=role.id,
            desde=date(2020, 1, 1),
        )
        session.add(ur)
        await session.flush()

        # Create role + permission for target (test:leer)
        role2 = Role(tenant_id=tid, nombre="Target Role", codigo="TARGET")
        session.add(role2)
        await session.flush()

        perm2 = Permission(tenant_id=tid, codigo="test:leer")
        session.add(perm2)
        await session.flush()

        rp2 = RolePermission(role_id=role2.id, permission_id=perm2.id)
        session.add(rp2)
        await session.flush()

        ur2 = UserRole(
            tenant_id=tid,
            user_id=target.id,
            role_id=role2.id,
            desde=date(2020, 1, 1),
        )
        session.add(ur2)
        await session.flush()

        data = {
            "tenant_id": tid,
            "admin_id": admin.id,
            "target_id": target.id,
            "admin_email": "admin@test.com",
            "admin_password": "AdminPass1!",
        }
        await session.commit()

    await engine.dispose()
    return data


def _get_app(client: AsyncClient):
    """Access the ASGI app wrapped by the test client's transport."""
    return client._transport.app


class TestGetCurrentUserImpersonation:
    """RED→GREEN: get_current_user with impersonation tokens."""

    async def _login_token(
        self, client: AsyncClient, email: str, password: str
    ) -> str:
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]

    async def test_normal_token_no_impersonation(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """get_current_user with normal token has is_impersonating=False."""
        _get_app(async_client).include_router(_test_router)

        token = await self._login_token(
            async_client,
            seed_impersonation["admin_email"],
            seed_impersonation["admin_password"],
        )
        resp = await async_client.get(
            "/test-whoami",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_impersonating"] is False
        assert data["user_id"] == str(seed_impersonation["admin_id"])

    async def test_impersonation_token_has_is_impersonating(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """get_current_user with impersonation token has is_impersonating=True and correct user."""
        _get_app(async_client).include_router(_test_router)

        # Create impersonation token directly (endpoint not built yet)
        token = create_impersonation_token(
            user_id=seed_impersonation["target_id"],
            impersonator_id=seed_impersonation["admin_id"],
            tenant_id=seed_impersonation["tenant_id"],
        )
        resp = await async_client.get(
            "/test-whoami",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_impersonating"] is True
        # The effective user should be the impersonated target
        assert data["user_id"] == str(seed_impersonation["target_id"])

    async def test_impersonation_uses_target_permissions(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """Under impersonation, loaded permissions are from impersonated user, not admin."""
        _get_app(async_client).include_router(_test_router)

        # Admin has impersonacion:usar, Target has test:leer
        token = create_impersonation_token(
            user_id=seed_impersonation["target_id"],
            impersonator_id=seed_impersonation["admin_id"],
            tenant_id=seed_impersonation["tenant_id"],
        )
        resp = await async_client.get(
            "/test-permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_impersonating"] is True
        # Should have the target's permissions (test:leer), NOT admin's (impersonacion:usar)
        assert "impersonacion:usar" not in data["permissions"]
        assert "test:leer" in data["permissions"]


class TestImpersonateEndpoints:
    """RED→GREEN: POST /api/auth/impersonate/start and /end."""

    async def _login_token(
        self, client: AsyncClient, email: str, password: str
    ) -> str:
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        return resp.json()["access_token"]

    async def test_start_success(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """Start impersonation returns 200 with tokens and logs audit."""
        token = await self._login_token(
            async_client,
            seed_impersonation["admin_email"],
            seed_impersonation["admin_password"],
        )
        resp = await async_client.post(
            "/api/auth/impersonate/start",
            json={"user_id": str(seed_impersonation["target_id"])},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "impersonation_token" in data
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify audit log was created
        from sqlalchemy import select
        from app.models import AuditLog
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.accion == "IMPERSONACION_INICIAR")
            )
            log = result.scalar_one_or_none()
            assert log is not None
            assert log.actor_id == seed_impersonation["admin_id"]
            assert log.impersonado_id == seed_impersonation["target_id"]
        await engine.dispose()

    async def test_start_without_permission_returns_403(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """User without impersonacion:usar gets 403."""
        # Target user doesn't have impersonacion:usar
        resp_login = await async_client.post(
            "/api/auth/login",
            json={"email": "target@test.com", "password": "TargetPass1!"},
        )
        assert resp_login.status_code == 200
        token = resp_login.json()["access_token"]

        resp = await async_client.post(
            "/api/auth/impersonate/start",
            json={"user_id": str(seed_impersonation["admin_id"])},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_start_nonexistent_user_returns_404(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """Impersonating a non-existent user returns 404."""
        token = await self._login_token(
            async_client,
            seed_impersonation["admin_email"],
            seed_impersonation["admin_password"],
        )
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await async_client.post(
            "/api/auth/impersonate/start",
            json={"user_id": fake_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_start_inactive_user_returns_400(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """Impersonating an inactive user returns 400."""
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            from sqlalchemy import select
            from app.models import User
            result = await session.execute(
                select(User).where(User.email == "target@test.com")
            )
            target = result.scalar_one()
            target.is_active = False
            await session.commit()
        await engine.dispose()

        token = await self._login_token(
            async_client,
            seed_impersonation["admin_email"],
            seed_impersonation["admin_password"],
        )
        resp = await async_client.post(
            "/api/auth/impersonate/start",
            json={"user_id": str(seed_impersonation["target_id"])},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    async def test_end_success(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """End impersonation returns 200 with new access token for impersonator."""
        # First, start impersonation via direct token creation
        imp_token = create_impersonation_token(
            user_id=seed_impersonation["target_id"],
            impersonator_id=seed_impersonation["admin_id"],
            tenant_id=seed_impersonation["tenant_id"],
        )
        resp = await async_client.post(
            "/api/auth/impersonate/end",
            headers={"Authorization": f"Bearer {imp_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify audit log was created
        from sqlalchemy import select
        from app.models import AuditLog
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await session.execute(
                select(AuditLog).where(AuditLog.accion == "IMPERSONACION_FINALIZAR")
            )
            log = result.scalar_one_or_none()
            assert log is not None
            assert log.actor_id == seed_impersonation["admin_id"]
            assert log.impersonado_id == seed_impersonation["target_id"]
        await engine.dispose()

    async def test_end_without_impersonation_returns_400(
        self, async_client: AsyncClient, seed_impersonation: dict
    ):
        """End impersonation when not impersonating returns 400."""
        token = await self._login_token(
            async_client,
            seed_impersonation["admin_email"],
            seed_impersonation["admin_password"],
        )
        resp = await async_client.post(
            "/api/auth/impersonate/end",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
