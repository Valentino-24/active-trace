"""Carreras admin router — CRUD for degree programmes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.repositories.carrera_repository import CarreraRepository
from app.schemas.carrera import (
    CarreraCreate,
    CarreraListResponse,
    CarreraResponse,
    CarreraUpdate,
)

router = APIRouter(tags=["admin"])


@router.get(
    "",
    response_model=CarreraListResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def list_carreras(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all carreras for the current tenant (paginated)."""
    repo = CarreraRepository(session=db, tenant_id=current_user.tenant_id)
    all_items = await repo.list()
    total = len(all_items)
    items = all_items[skip : skip + limit]
    return CarreraListResponse(
        items=[CarreraResponse.model_validate(c) for c in items],
        total=total,
    )


@router.post(
    "",
    response_model=CarreraResponse,
    status_code=201,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def create_carrera(
    body: CarreraCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new carrera."""
    repo = CarreraRepository(session=db, tenant_id=current_user.tenant_id)

    # Check uniqueness
    existing = await repo.get_by_codigo(body.codigo)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una carrera con código '{body.codigo}'",
        )

    instance = await repo.create(codigo=body.codigo, nombre=body.nombre)
    return CarreraResponse.model_validate(instance)


@router.get(
    "/{carrera_id}",
    response_model=CarreraResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def get_carrera(
    carrera_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a carrera by ID."""
    repo = CarreraRepository(session=db, tenant_id=current_user.tenant_id)
    instance = await repo.get(carrera_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    return CarreraResponse.model_validate(instance)


@router.put(
    "/{carrera_id}",
    response_model=CarreraResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def update_carrera(
    carrera_id: uuid.UUID,
    body: CarreraUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a carrera."""
    repo = CarreraRepository(session=db, tenant_id=current_user.tenant_id)

    update_kwargs = body.model_dump(exclude_unset=True)
    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    instance = await repo.update(carrera_id, **update_kwargs)
    if instance is None:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    return CarreraResponse.model_validate(instance)


@router.delete(
    "/{carrera_id}",
    status_code=204,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def delete_carrera(
    carrera_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a carrera."""
    repo = CarreraRepository(session=db, tenant_id=current_user.tenant_id)
    deleted = await repo.soft_delete(carrera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    return None
