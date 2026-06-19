"""Permission resolution engine and authorization guard.

Provides:
- get_user_permissions: Resolves effective permissions for a user.
- require_permission: FastAPI dependency factory for endpoint protection.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rbac import Permission, RolePermission, UserRole
from app.models.user import User


async def get_user_permissions(db: AsyncSession, user: User) -> set[str]:
    """Resolve the effective permission codes for a user.

    Queries all active UserRole assignments (not soft-deleted, within vigency
    range), and returns the union of all associated Permission codes.

    Args:
        db: Database session.
        user: The user whose permissions to resolve.

    Returns:
        A set of permission code strings (e.g. ``{"calificaciones:importar"}``).
    """
    today = date.today()

    # Fetch active UserRoles for this user
    stmt = (
        select(UserRole)
        .where(UserRole.user_id == user.id)
        .where(UserRole.deleted_at.is_(None))
        .where(UserRole.desde <= today)
        .where(
            (UserRole.hasta.is_(None)) | (UserRole.hasta >= today)
        )
        .options(selectinload(UserRole.role))
    )
    result = await db.execute(stmt)
    active_roles = result.scalars().all()

    if not active_roles:
        return set()

    # Collect role IDs
    role_ids = {ur.role_id for ur in active_roles}

    # Fetch all Permission codes associated with those roles
    perm_stmt = (
        select(Permission.codigo)
        .join(RolePermission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.role_id.in_(role_ids))
    )
    perm_result = await db.execute(perm_stmt)
    return {row[0] for row in perm_result.fetchall()}


def require_permission(permiso: str):
    """FastAPI dependency factory that guards an endpoint by permission.

    Usage::

        @router.get("/calificaciones")
        async def list_calificaciones(
            _: None = Depends(require_permission("calificaciones:importar")),
        ):
            ...

    Args:
        permiso: The permission code to check (``modulo:accion`` format).

    Returns:
        A FastAPI dependency that raises HTTPException(403) if the user
        does not have the required permission.
    """
    # Lazy import to avoid circular dependency at module level:
    # permissions.py → dependencies.py → permissions.py
    from app.core.dependencies import get_current_user as _get_current_user

    async def _require(
        user: User = Depends(_get_current_user),
    ) -> None:
        if permiso not in user.permissions:
            raise HTTPException(status_code=403, detail="Forbidden")
    return _require
