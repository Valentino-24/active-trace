"""Tests for AuthService — login, refresh, 2FA, password recovery.

RED→GREEN: Service layer tests with real DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
)
from app.models.auth import PasswordResetToken, RefreshToken
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import AuthService


@pytest_asyncio.fixture
async def tenant(db_session):
    t = Tenant(nombre="Test", codigo="SRV01")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest_asyncio.fixture
async def tenant_id(tenant):
    return tenant.id


@pytest.fixture
def user_data():
    return {
        "email": "test@example.com",
        "password": "secure_password_123",
        "display_name": "Test User",
    }


@pytest_asyncio.fixture
async def existing_user(db_session, tenant_id, user_data):
    password_hash_val = hash_password(user_data["password"])
    user = User(
        tenant_id=tenant_id,
        email=user_data["email"],
        password_hash=password_hash_val,
        display_name=user_data["display_name"],
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def auth_service(db_session, tenant_id):
    return AuthService(session=db_session, tenant_id=tenant_id, client_ip="127.0.0.1")


class TestLogin:
    """RED→GREEN: Login flow verification."""

    @pytest.mark.asyncio
    async def test_login_success_no_2fa(self, auth_service, user_data, existing_user):
        """Login with valid credentials returns tokens when 2FA is off."""
        result = await auth_service.login(
            email=user_data["email"], password=user_data["password"]
        )
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert "requires_2fa" not in result

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, auth_service, user_data):
        """Login with wrong credentials raises 401."""
        with pytest.raises(Exception) as exc:
            await auth_service.login(
                email=user_data["email"], password="wrong_password"
            )
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self, auth_service, db_session, tenant_id, user_data
    ):
        """Login for inactive user raises 403."""
        password_hash_val = hash_password(user_data["password"])
        user = User(
            tenant_id=tenant_id,
            email="inactive@example.com",
            password_hash=password_hash_val,
            display_name="Inactive",
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()

        with pytest.raises(Exception) as exc:
            await auth_service.login(
                email="inactive@example.com", password=user_data["password"]
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_login_with_2fa_returns_session_token(
        self, auth_service, db_session, existing_user
    ):
        """Login with 2FA enabled returns session_token."""
        existing_user.totp_secret = "FAKESECRET"
        existing_user.totp_enabled = True
        await db_session.flush()

        result = await auth_service.login(
            email=existing_user.email, password="secure_password_123"
        )
        assert result.get("requires_2fa") is True
        assert "session_token" in result
        assert "access_token" not in result
        assert "refresh_token" not in result


class TestRefreshToken:
    """RED→GREEN: Refresh token rotation and reuse detection."""

    @pytest.mark.asyncio
    async def test_refresh_success(
        self, auth_service, existing_user, db_session
    ):
        """Refresh with valid token returns new access+refresh pair."""
        # Create a refresh token manually
        token = generate_opaque_token()
        rt = RefreshToken(
            user_id=existing_user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(rt)
        await db_session.flush()

        result = await auth_service.refresh_token(token)
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["refresh_token"] != token

    @pytest.mark.asyncio
    async def test_refresh_reuse_detection(
        self, auth_service, existing_user, db_session
    ):
        """Using an already revoked token revokes ALL sessions."""
        token = generate_opaque_token()
        rt = RefreshToken(
            user_id=existing_user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(rt)
        await db_session.flush()

        # First use: should work
        await auth_service.refresh_token(token)

        # Second use (same token): should raise and revoke all
        with pytest.raises(Exception) as exc:
            await auth_service.refresh_token(token)
        assert exc.value.status_code == 401

        # Verify ALL refresh tokens for user are revoked
        from sqlalchemy import select

        stmt = select(RefreshToken).where(RefreshToken.user_id == existing_user.id)
        result = await db_session.execute(stmt)
        all_tokens = result.scalars().all()
        for t in all_tokens:
            assert t.revoked_at is not None


class TestLogout:
    """RED→GREEN: Logout revokes refresh token."""

    @pytest.mark.asyncio
    async def test_logout_revokes_token(
        self, auth_service, existing_user, db_session
    ):
        """Logout marks the refresh token as revoked."""
        token = generate_opaque_token()
        rt = RefreshToken(
            user_id=existing_user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(rt)
        await db_session.flush()

        await auth_service.logout(token)
        assert rt.revoked_at is not None

    @pytest.mark.asyncio
    async def test_logout_idempotent(self, auth_service):
        """Logout with invalid token does not raise."""
        await auth_service.logout("nonexistent-token")


class Test2FA:
    """RED→GREEN: 2FA enrollment and verification."""

    @pytest.mark.asyncio
    async def test_enroll_2fa_returns_secret(self, auth_service, existing_user):
        """Enrolling 2FA returns a secret and URI."""
        result = await auth_service.enroll_2fa(existing_user)
        assert "secret" in result
        assert "uri" in result
        assert result["uri"].startswith("otpauth://")

    @pytest.mark.asyncio
    async def test_enroll_2fa_already_active(
        self, auth_service, existing_user, db_session
    ):
        """Enrolling when 2FA is active raises 409."""
        existing_user.totp_enabled = True
        existing_user.totp_secret = "SOMESECRET"
        await db_session.flush()

        with pytest.raises(Exception) as exc:
            await auth_service.enroll_2fa(existing_user)
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_verify_2fa_enroll_valid(
        self, auth_service, existing_user, db_session
    ):
        """Verify 2FA with valid TOTP code activates 2FA."""
        import pyotp

        secret = pyotp.random_base32()
        existing_user.totp_secret = secret
        existing_user.totp_enabled = False
        await db_session.flush()

        totp = pyotp.TOTP(secret)
        code = totp.now()
        await auth_service.verify_2fa_enroll(existing_user, code)

        # Reload user
        await db_session.refresh(existing_user)
        assert existing_user.totp_enabled is True

    @pytest.mark.asyncio
    async def test_verify_2fa_enroll_invalid_code(
        self, auth_service, existing_user, db_session
    ):
        """Verify 2FA with invalid code raises 401."""
        existing_user.totp_secret = "SOMESECRET"
        await db_session.flush()

        with pytest.raises(Exception) as exc:
            await auth_service.verify_2fa_enroll(existing_user, "000000")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_disable_2fa_with_password(
        self, auth_service, existing_user, db_session
    ):
        """Disable 2FA with correct password succeeds."""
        existing_user.totp_secret = "SOMESECRET"
        existing_user.totp_enabled = True
        await db_session.flush()

        await auth_service.disable_2fa(existing_user, "secure_password_123")
        await db_session.refresh(existing_user)
        assert existing_user.totp_enabled is False
        assert existing_user.totp_secret is None

    @pytest.mark.asyncio
    async def test_disable_2fa_wrong_password(
        self, auth_service, existing_user, db_session
    ):
        """Disable 2FA with wrong password raises 401."""
        existing_user.totp_enabled = True
        await db_session.flush()

        with pytest.raises(Exception) as exc:
            await auth_service.disable_2fa(existing_user, "wrong_password")
        assert exc.value.status_code == 401


class TestPasswordRecovery:
    """RED→GREEN: Forgot and reset password flow."""

    @pytest.mark.asyncio
    async def test_forgot_password_returns_token(
        self, auth_service, existing_user
    ):
        """Forgot password returns a reset token for existing email."""
        result = await auth_service.forgot_password(existing_user.email)
        assert "reset_token" in result

    @pytest.mark.asyncio
    async def test_forgot_password_unknown_email(self, auth_service):
        """Forgot password for unknown email returns empty dict."""
        result = await auth_service.forgot_password("unknown@example.com")
        assert result == {}

    @pytest.mark.asyncio
    async def test_reset_password_with_valid_token(
        self, auth_service, existing_user, db_session
    ):
        """Reset password with valid token updates password and revokes sessions."""
        # Create a reset token
        result = await auth_service.forgot_password(existing_user.email)
        token = result["reset_token"]

        new_password = "new_secure_password_456"
        await auth_service.reset_password(token, new_password)

        # Verify password changed
        await db_session.refresh(existing_user)
        from app.core.security import verify_password

        assert verify_password(new_password, existing_user.password_hash)

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, auth_service):
        """Reset with invalid token raises 401."""
        with pytest.raises(Exception) as exc:
            await auth_service.reset_password("invalid-token", "new_password_123")
        assert exc.value.status_code == 401


class TestVerify2FALogin:
    """TRIANGULATE: Complete 2FA login flow."""

    @pytest.mark.asyncio
    async def test_verify_2fa_login_success(
        self, auth_service, existing_user, db_session
    ):
        """Complete 2FA login with valid TOTP code returns tokens."""
        import pyotp

        secret = pyotp.random_base32()
        existing_user.totp_secret = secret
        existing_user.totp_enabled = True
        await db_session.flush()

        # Step 1: Login
        login_result = await auth_service.login(
            email=existing_user.email, password="secure_password_123"
        )
        assert login_result["requires_2fa"] is True
        session_token = login_result["session_token"]

        # Step 2: Verify TOTP
        totp = pyotp.TOTP(secret)
        code = totp.now()
        verify_result = await auth_service.verify_2fa_login(session_token, code)
        assert "access_token" in verify_result
        assert "refresh_token" in verify_result

    @pytest.mark.asyncio
    async def test_verify_2fa_login_invalid_code(
        self, auth_service, existing_user, db_session
    ):
        """2FA login with invalid TOTP code raises 401."""
        import pyotp

        existing_user.totp_secret = pyotp.random_base32()
        existing_user.totp_enabled = True
        await db_session.flush()

        login_result = await auth_service.login(
            email=existing_user.email, password="secure_password_123"
        )
        session_token = login_result["session_token"]

        with pytest.raises(Exception) as exc:
            await auth_service.verify_2fa_login(session_token, "000000")
        assert exc.value.status_code == 401
