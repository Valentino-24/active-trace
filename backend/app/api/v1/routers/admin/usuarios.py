"""Usuarios admin router — CRUD for extended user profiles with PII.

All endpoints require the ``usuarios:*`` permission.
PII fields are encrypted at rest and decrypted on detail response.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.usuario import (
    UserCreate,
    UserListResponse,
    UserListResponseItem,
    UserResponse,
    UserUpdate,
)

router = APIRouter(tags=["admin"])


def _mask_email(email: str) -> str:
    """Mask an email for list display: jo****@example.com."""
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked = local[0] + "**"
    else:
        masked = local[:2] + "**"
    return f"{masked}@{domain}"


@router.get(
    "",
    response_model=UserListResponse,
    dependencies=[Depends(require_permission("usuarios:list"))],
)
async def list_usuarios(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    estado: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all users for the current tenant (paginated, no full PII)."""
    repo = UserRepository(session=db, tenant_id=current_user.tenant_id)
    users, total = await repo.list_users(skip=skip, limit=limit, estado=estado)

    items = []
    for u in users:
        items.append(
            UserListResponseItem(
                id=u.id,
                tenant_id=u.tenant_id,
                email_masked=_mask_email(u.email),
                display_name=u.display_name,
                nombre=u.nombre,
                apellidos=u.apellidos,
                legajo=u.legajo,
                facturador=u.facturador,
                estado=u.estado,
                is_active=u.is_active,
            )
        )

    return UserListResponse(items=items, total=total)


@router.post(
    "",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(require_permission("usuarios:create"))],
)
async def create_usuario(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new user with PII."""
    repo = UserRepository(session=db, tenant_id=current_user.tenant_id)

    # Check email uniqueness
    if await repo.email_exists(body.email):
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un usuario con email '{body.email}'",
        )

    password_hash = hash_password(body.password)
    create_kwargs = body.model_dump(
        exclude={"password"},
        exclude_none=True,
    )

    user = await repo.create_user(
        email=create_kwargs.pop("email"),
        password_hash=password_hash,
        **create_kwargs,
    )

    return UserResponse.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("usuarios:list"))],
)
async def get_usuario(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a user by ID with full PII (decrypted)."""
    repo = UserRepository(session=db, tenant_id=current_user.tenant_id)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_permission("usuarios:update"))],
)
async def update_usuario(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a user's data (PII fields encrypted on save)."""
    repo = UserRepository(session=db, tenant_id=current_user.tenant_id)

    # Check existence first
    existing = await repo.get(user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    update_kwargs = body.model_dump(exclude_unset=True, exclude_none=True)

    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    # If email is being changed, check uniqueness
    if "email" in update_kwargs:
        new_email = update_kwargs["email"]
        if new_email != existing.email:
            if await repo.email_exists(new_email):
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un usuario con email '{new_email}'",
                )

    # Hash password if provided
    if "password" in update_kwargs:
        update_kwargs["password_hash"] = hash_password(update_kwargs.pop("password"))

    user = await repo.update_user(user_id, **update_kwargs)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return UserResponse.model_validate(user)
