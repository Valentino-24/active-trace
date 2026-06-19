"""Auth service — login, 2FA, refresh rotation, password recovery.

All authentication business logic lives here.
Routers delegate to this service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import RateLimiter
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)
from app.models.auth import PasswordResetToken, RefreshToken
from app.models.user import User
from app.repositories.user_repository import UserRepository

# ── Constants ────────────────────────────────────────────────────────────────

SESSION_TOKEN_EXPIRE_MINUTES = 5
REFRESH_TOKEN_EXPIRE_DAYS = 7
RESET_TOKEN_EXPIRE_MINUTES = 30

rate_limiter = RateLimiter()


class AuthService:
    """Handles authentication flows.

    Every method that needs DB access receives session and tenant_id.
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        client_ip: str = "unknown",
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._client_ip = client_ip
        self._user_repo = UserRepository(session=session, tenant_id=tenant_id)

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _create_tokens_for_user(
        user: User,
    ) -> dict[str, str]:
        """Create access and refresh tokens for a given user.

        Returns dict with access_token, refresh_token, token_type.
        """
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(user.tenant_id),
                "roles": [],
            }
        )
        return {"access_token": access_token, "token_type": "bearer"}

    async def _save_refresh_token(self, user_id: uuid.UUID) -> str:
        """Generate, persist, and return an opaque refresh token."""
        token = generate_opaque_token()
        token_hash = hash_token(token)
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self._session.add(rt)
        await self._session.flush()
        return token

    async def _revoke_all_user_refresh_tokens(self, user_id: uuid.UUID) -> None:
        """Revoke all active refresh tokens for a user."""
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        result = await self._session.execute(stmt)
        tokens = result.scalars().all()
        now = datetime.now(UTC)
        for rt in tokens:
            rt.revoked_at = now
        await self._session.flush()

    # ── Login ───────────────────────────────────────────────────────

    async def login(
        self, email: str, password: str
    ) -> dict:
        """Authenticate a user with email and password.

        Returns:
            If 2FA disabled: dict with access_token, refresh_token, token_type.
            If 2FA enabled: dict with requires_2fa=True, session_token.
            Raises 401 on bad credentials, 403 on inactive user.
        """
        # Rate limit check
        if not rate_limiter.check(self._client_ip, email):
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos. Intente nuevamente en 60 segundos.",
            )

        # Use email_hash for lookup (email column is AES-256-GCM encrypted)
        user = await self._user_repo.get_by_email(email)

        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Credenciales inválidas.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="Cuenta desactivada.",
            )

        # Check 2FA
        if user.totp_enabled:
            session_token = create_access_token(
                data={
                    "sub": str(user.id),
                    "tenant_id": str(user.tenant_id),
                    "purpose": "2fa_login",
                },
                expires_delta=timedelta(minutes=SESSION_TOKEN_EXPIRE_MINUTES),
            )
            return {"requires_2fa": True, "session_token": session_token}

        # No 2FA — issue tokens directly
        tokens = self._create_tokens_for_user(user)
        refresh = await self._save_refresh_token(user.id)
        tokens["refresh_token"] = refresh
        return tokens

    async def verify_2fa_login(
        self, session_token: str, totp_code: str
    ) -> dict:
        """Complete a 2FA-gated login by verifying the TOTP code.

        Args:
            session_token: JWT from the login step.
            totp_code: 6-digit TOTP code.

        Returns:
            dict with access_token, refresh_token on success.

        Raises:
            HTTPException 401 on invalid session or TOTP code.
        """
        try:
            payload = decode_access_token(session_token)
        except Exception:
            raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")

        if payload.get("purpose") != "2fa_login":
            raise HTTPException(status_code=401, detail="Token de sesión inválido.")

        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])

        # Use the tenant_id from the session token to recreate the correct repo
        local_repo = UserRepository(session=self._session, tenant_id=tenant_id)
        user = await local_repo.get_by_id(user_id)

        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo.")

        if not user.totp_secret or not verify_totp(user.totp_secret, totp_code):
            raise HTTPException(status_code=401, detail="Código TOTP inválido.")

        tokens = self._create_tokens_for_user(user)
        refresh = await self._save_refresh_token(user.id)
        tokens["refresh_token"] = refresh
        return tokens

    # ── Refresh ─────────────────────────────────────────────────────

    async def refresh_token(self, refresh_token_str: str) -> dict:
        """Rotate a refresh token: revoke old, issue new pair.

        If the token was already revoked (reuse detected), revoke ALL
        active sessions for that user.

        Args:
            refresh_token_str: The opaque refresh token.

        Returns:
            dict with new access_token, refresh_token.
        """
        token_hash = hash_token(refresh_token_str)

        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        rt = result.scalar_one_or_none()

        if rt is None:
            raise HTTPException(status_code=401, detail="Token de refresco inválido.")

        # Check expiry
        if rt.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=401, detail="Token de refresco expirado.")

        # Reuse detection
        if rt.revoked_at is not None:
            # Token was already revoked — this is a reuse attempt
            await self._revoke_all_user_refresh_tokens(rt.user_id)
            raise HTTPException(
                status_code=401,
                detail="Token de refresco reutilizado. Todas las sesiones fueron revocadas.",
            )

        # Revoke the current token
        rt.revoked_at = datetime.now(UTC)

        # Get user info to create new tokens
        # Need to fetch user to get tenant_id — use direct query
        stmt_user = select(User).where(User.id == rt.user_id)
        result_user = await self._session.execute(stmt_user)
        user = result_user.scalar_one_or_none()

        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo.")

        # Issue new tokens
        tokens = self._create_tokens_for_user(user)
        new_refresh = await self._save_refresh_token(user.id)
        tokens["refresh_token"] = new_refresh
        await self._session.flush()
        return tokens

    # ── Logout ──────────────────────────────────────────────────────

    async def logout(self, refresh_token_str: str) -> None:
        """Revoke a refresh token (idempotent).

        Args:
            refresh_token_str: The opaque refresh token.
        """
        token_hash = hash_token(refresh_token_str)
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self._session.execute(stmt)
        rt = result.scalar_one_or_none()

        if rt is not None and rt.revoked_at is None:
            rt.revoked_at = datetime.now(UTC)
            await self._session.flush()
        # Idempotent: even if not found or already revoked, return success

    # ── 2FA Management ──────────────────────────────────────────────

    async def enroll_2fa(self, user: User) -> dict:
        """Generate a TOTP secret and return provisioning URI.

        Args:
            user: The authenticated user.

        Returns:
            dict with secret and URI.

        Raises:
            HTTPException 409 if 2FA already active.
        """
        if user.totp_enabled:
            raise HTTPException(
                status_code=409,
                detail="La verificación en dos pasos ya está activa.",
            )

        secret = generate_totp_secret()
        uri = get_totp_uri(secret, user.email)

        # Store encrypted secret — for MVP, store as-is (AES-256 will be added
        # when the encryption key is available in the service context)
        await self._user_repo.update_totp(
            user.id, totp_secret=secret, totp_enabled=False
        )

        return {"secret": secret, "uri": uri}

    async def verify_2fa_enroll(self, user: User, totp_code: str) -> None:
        """Verify a TOTP code to activate 2FA enrollment.

        Args:
            user: The authenticated user.
            totp_code: 6-digit TOTP code.

        Raises:
            HTTPException 401 if code is invalid.
        """
        if not user.totp_secret:
            raise HTTPException(
                status_code=400,
                detail="No hay secreto TOTP pendiente de verificación.",
            )

        if not verify_totp(user.totp_secret, totp_code):
            raise HTTPException(status_code=401, detail="Código TOTP inválido.")

        await self._user_repo.update_totp(
            user.id, totp_secret=user.totp_secret, totp_enabled=True
        )

    async def disable_2fa(self, user: User, password: str) -> None:
        """Disable 2FA after verifying the user's password.

        Args:
            user: The authenticated user.
            password: Current password for verification.

        Raises:
            HTTPException 401 if password is wrong.
        """
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

        await self._user_repo.update_totp(
            user.id, totp_secret=None, totp_enabled=False
        )

    # ── Password Recovery ───────────────────────────────────────────

    async def forgot_password(self, email: str) -> dict:
        """Generate a password reset token.

        MVP: returns the token in the response body.
        In production, this would trigger an email send.

        Args:
            email: User's email.

        Returns:
            dict with reset_token (if user exists) or empty dict.
        """
        user = await self._user_repo.get_by_email(email)

        if user is None:
            # Generic response to not reveal email existence
            return {}

        # Invalidate any existing reset tokens for this user
        stmt = (
            select(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > datetime.now(UTC),
            )
        )
        result = await self._session.execute(stmt)
        existing_tokens = result.scalars().all()
        now = datetime.now(UTC)
        for pt in existing_tokens:
            pt.used_at = now

        # Create new reset token
        token = generate_opaque_token()
        token_hash_val = hash_token(token)
        prt = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash_val,
            expires_at=now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
        )
        self._session.add(prt)
        await self._session.flush()

        return {"reset_token": token}

    async def reset_password(self, token: str, new_password: str) -> None:
        """Reset a user's password using a reset token.

        Validates the token, updates the password hash, marks token as used,
        and revokes all active sessions.

        Args:
            token: The opaque reset token.
            new_password: New plain-text password.

        Raises:
            HTTPException 401 if token is invalid, expired, or already used.
        """
        token_hash_val = hash_token(token)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash_val
        )
        result = await self._session.execute(stmt)
        prt = result.scalar_one_or_none()

        if prt is None:
            raise HTTPException(status_code=401, detail="Token de recuperación inválido.")

        if prt.used_at is not None:
            raise HTTPException(status_code=401, detail="Token de recuperación ya utilizado.")

        if prt.expires_at < datetime.now(UTC):
            raise HTTPException(status_code=401, detail="Token de recuperación expirado.")

        # Mark as used
        prt.used_at = datetime.now(UTC)

        # Update password
        new_hash = hash_password(new_password)
        stmt_user = select(User).where(User.id == prt.user_id)
        result_user = await self._session.execute(stmt_user)
        user = result_user.scalar_one_or_none()

        if user is None:
            raise HTTPException(status_code=401, detail="Usuario no encontrado.")

        user.password_hash = new_hash

        # Revoke all active sessions
        await self._revoke_all_user_refresh_tokens(user.id)
        await self._session.flush()
