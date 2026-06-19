"""Auth router — login, 2FA, refresh, logout, password recovery.

All endpoints under /api/auth prefix.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_optional_user
from app.core.permissions import require_permission
from app.core.security import create_access_token, create_impersonation_token
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit_service import log_action
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


# ── Request/Response schemas ───────────────────────────────────────────────


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    requires_2fa: bool | None = None
    session_token: str | None = None


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class RefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class Enroll2FAResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret: str
    uri: str


class Verify2FARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_token: str
    totp_code: str = Field(pattern=r"^\d{6}$")


class Disable2FARequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1)


class ForgotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ForgotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reset_token: str | None = None


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str = Field(min_length=8)


class ImpersonateStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class ImpersonateStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    impersonation_token: str
    access_token: str
    token_type: str


class ImpersonateEndResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str


# ── Helper ────────────────────────────────────────────────────────────────


async def _resolve_tenant_id(db: AsyncSession, request: Request) -> uuid.UUID:
    """Resolve the tenant_id for this request.

    MVP: reads the first available tenant.
    C-04 will replace this with JWT-based tenant resolution.
    """
    tenant_id: uuid.UUID | None = getattr(request.state, "tenant_id", None)
    if tenant_id is not None:
        return tenant_id

    result = await db.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=400, detail="No tenant configured")
    return tenant.id


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password.

    Returns access+refresh tokens, or requires_2fa+session_token if 2FA enabled.
    """
    tenant_id = await _resolve_tenant_id(db, request)
    client_ip = request.client.host if request.client else "unknown"
    service = AuthService(session=db, tenant_id=tenant_id, client_ip=client_ip)
    return await service.login(email=body.email, password=body.password)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Rotate a refresh token and return a new access+refresh pair."""
    tenant_id = await _resolve_tenant_id(db, request)
    service = AuthService(session=db, tenant_id=tenant_id)
    return await service.refresh_token(body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    body: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Revoke a refresh token (idempotent)."""
    tenant_id = await _resolve_tenant_id(db, request)
    service = AuthService(session=db, tenant_id=tenant_id)
    await service.logout(body.refresh_token)
    return None


@router.post("/2fa/enroll", response_model=Enroll2FAResponse)
async def enroll_2fa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a TOTP secret and return provisioning URI."""
    service = AuthService(session=db, tenant_id=current_user.tenant_id)
    return await service.enroll_2fa(current_user)


@router.post("/2fa/verify")
async def verify_2fa(
    body: Verify2FARequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    """Verify a TOTP code.

    Two purposes:
    1. Complete 2FA enrollment (authenticated user, session_token optional)
    2. Complete 2FA login gate (unauthenticated, session_token from login)
    """
    # If user is authenticated and has a pending TOTP secret, this is enrollment
    if current_user is not None and current_user.totp_secret and not current_user.totp_enabled:
        service = AuthService(session=db, tenant_id=current_user.tenant_id)
        await service.verify_2fa_enroll(current_user, body.totp_code)
        return {"detail": "Verificación en dos pasos activada."}

    # Otherwise, this is a 2FA login gate
    tenant_id = await _resolve_tenant_id(db, request)
    service = AuthService(session=db, tenant_id=tenant_id)
    return await service.verify_2fa_login(body.session_token, body.totp_code)


@router.post("/2fa/disable", status_code=204)
async def disable_2fa(
    body: Disable2FARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable 2FA with password verification."""
    service = AuthService(session=db, tenant_id=current_user.tenant_id)
    await service.disable_2fa(current_user, body.password)
    return None


@router.post("/forgot", response_model=ForgotResponse)
async def forgot_password(
    body: ForgotRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset token (MVP: returned in response)."""
    tenant_id = await _resolve_tenant_id(db, request)
    service = AuthService(session=db, tenant_id=tenant_id)
    return await service.forgot_password(body.email)


@router.post("/impersonate/start", response_model=ImpersonateStartResponse)
async def impersonate_start(
    body: ImpersonateStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("impersonacion:usar")),
    current_user: User = Depends(get_current_user),
):
    """Start an impersonation session.

    Requires `impersonacion:usar` permission.
    Returns an impersonation token (for the /end endpoint) and a new
    access token for the impersonated session.
    """
    # Load the target user
    result = await db.execute(select(User).where(User.id == body.user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="El usuario objetivo está inactivo")

    # Create the impersonation token (for ending the session)
    impersonation_token = create_impersonation_token(
        user_id=target.id,
        impersonator_id=current_user.id,
        tenant_id=target.tenant_id,
    )

    # Create a new access token for the impersonated user
    access_token = create_access_token(
        data={
            "sub": str(target.id),
            "impersonator_id": str(current_user.id),
            "tenant_id": str(target.tenant_id),
        }
    )

    # Log the audit action
    client_ip = request.client.host if request.client else None
    await log_action(
        db=db,
        actor_id=current_user.id,
        tenant_id=current_user.tenant_id,
        accion="IMPERSONACION_INICIAR",
        impersonado_id=target.id,
        ip=client_ip,
    )

    return ImpersonateStartResponse(
        impersonation_token=impersonation_token,
        access_token=access_token,
        token_type="bearer",
    )


@router.post("/impersonate/end", response_model=ImpersonateEndResponse)
async def impersonate_end(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """End an impersonation session.

    Requires an impersonation token (with `impersonator_id` claim).
    Returns a new access token for the impersonator (real user).
    """
    if not current_user.is_impersonating:
        raise HTTPException(
            status_code=400,
            detail="No hay una sesión de impersonación activa",
        )

    impersonator = current_user._impersonator_user

    # Create a new access token for the impersonator
    access_token = create_access_token(
        data={
            "sub": str(impersonator.id),
            "tenant_id": str(impersonator.tenant_id),
        }
    )

    # Log the audit action
    client_ip = request.client.host if request.client else None
    await log_action(
        db=db,
        actor_id=impersonator.id,
        tenant_id=impersonator.tenant_id,
        accion="IMPERSONACION_FINALIZAR",
        impersonado_id=current_user.id,
        ip=client_ip,
    )

    return ImpersonateEndResponse(access_token=access_token, token_type="bearer")


@router.post("/reset", status_code=204)
async def reset_password(
    body: ResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a recovery token."""
    tenant_id = await _resolve_tenant_id(db, request)
    service = AuthService(session=db, tenant_id=tenant_id)
    await service.reset_password(body.token, body.new_password)
    return None
