"""Materias admin router — CRUD for subject catalogue."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.repositories.materia_repository import MateriaRepository
from app.schemas.materia import (
    MateriaCreate,
    MateriaListResponse,
    MateriaResponse,
    MateriaUpdate,
)

router = APIRouter(tags=["admin"])


@router.get(
    "",
    response_model=MateriaListResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def list_materias(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all materias for the current tenant (paginated)."""
    repo = MateriaRepository(session=db, tenant_id=current_user.tenant_id)
    all_items = await repo.list()
    total = len(all_items)
    items = all_items[skip : skip + limit]
    return MateriaListResponse(
        items=[MateriaResponse.model_validate(m) for m in items],
        total=total,
    )


@router.post(
    "",
    response_model=MateriaResponse,
    status_code=201,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def create_materia(
    body: MateriaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new materia."""
    repo = MateriaRepository(session=db, tenant_id=current_user.tenant_id)

    # Check uniqueness
    existing = await repo.get_by_codigo(body.codigo)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe una materia con código '{body.codigo}'",
        )

    instance = await repo.create(codigo=body.codigo, nombre=body.nombre)
    return MateriaResponse.model_validate(instance)


@router.get(
    "/{materia_id}",
    response_model=MateriaResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def get_materia(
    materia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a materia by ID."""
    repo = MateriaRepository(session=db, tenant_id=current_user.tenant_id)
    instance = await repo.get(materia_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return MateriaResponse.model_validate(instance)


@router.put(
    "/{materia_id}",
    response_model=MateriaResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def update_materia(
    materia_id: uuid.UUID,
    body: MateriaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a materia."""
    repo = MateriaRepository(session=db, tenant_id=current_user.tenant_id)

    update_kwargs = body.model_dump(exclude_unset=True)
    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    instance = await repo.update(materia_id, **update_kwargs)
    if instance is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return MateriaResponse.model_validate(instance)


@router.delete(
    "/{materia_id}",
    status_code=204,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def delete_materia(
    materia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a materia."""
    repo = MateriaRepository(session=db, tenant_id=current_user.tenant_id)
    deleted = await repo.soft_delete(materia_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    return None
