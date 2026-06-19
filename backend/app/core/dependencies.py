"""FastAPI dependency injection.

Current implementations:
    - get_db: Yields an async database session per request.
    - get_current_user: Resolve identity from JWT (Bearer token).
    - get_optional_user: Same but returns None if no token (public endpoints).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import get_user_permissions
from app.core.security import decode_access_token
from app.models.user import User

# OAuth2 Bearer token scheme
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yields an async DB session from the factory stored in app.state.

    Opens a session, yields it to the request handler,
    commits on success, rolls back on exception, and always closes.

    Args:
        request: FastAPI Request (used to access app.state).

    Yields:
        AsyncSession for the request.
    """
    session_factory = request.app.state.async_session_factory
    session: AsyncSession = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated User from a JWT Bearer token.

    Extracts the token from Authorization header, decodes it,
    resolves the User from the database, and verifies the account is active.

    Returns:
        The authenticated User.

    Raises:
        HTTPException 403: No Authorization header.
        HTTPException 401: Invalid, expired token, or inactive user.
    """
    if credentials is None:
        raise HTTPException(
            status_code=403,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o expirado",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido")

    from uuid import UUID

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Token inválido")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    # Load effective permissions into the user object
    user.permissions = await get_user_permissions(db, user)

    # ── Impersonation support ──────────────────────────────────────────
    # If the JWT has an impersonator_id claim, load the impersonator user
    # and attach it to the impersonated user's _impersonator_user attribute.
    # This makes user.is_impersonating return True.
    impersonator_id = payload.get("impersonator_id")
    if impersonator_id is not None:
        try:
            imp_uuid = UUID(impersonator_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="Token inválido")

        result = await db.execute(select(User).where(User.id == imp_uuid))
        impersonator = result.scalar_one_or_none()

        if impersonator is None or not impersonator.is_active:
            raise HTTPException(
                status_code=401, detail="Usuario impersonador no encontrado o inactivo"
            )

        user._impersonator_user = impersonator

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Resolve user from JWT if present, return None otherwise.

    Unlike get_current_user, this does NOT raise on missing token.
    It silently returns None for unauthenticated requests.

    Returns:
        User if token is valid, None otherwise.
    """
    if credentials is None:
        return None

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    from uuid import UUID

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user
