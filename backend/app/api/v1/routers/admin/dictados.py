"""Dictados admin router — CRUD for teaching instances."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.carrera import Carrera
from app.models.dictado import Dictado
from app.models.materia import Materia
from app.models.user import User
from app.repositories.dictado_repository import DictadoRepository
from app.schemas.dictado import (
    DictadoCreate,
    DictadoListResponse,
    DictadoResponse,
    DictadoUpdate,
)

router = APIRouter(tags=["admin"])


@router.get(
    "",
    response_model=DictadoListResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def list_dictados(
    materia_id: uuid.UUID | None = Query(default=None),
    cohorte_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List dictados for the current tenant, optionally filtered."""
    repo = DictadoRepository(session=db, tenant_id=current_user.tenant_id)

    if materia_id is not None:
        all_items = await repo.list_by_materia(materia_id)
    elif cohorte_id is not None:
        all_items = await repo.list_by_cohorte(cohorte_id)
    else:
        all_items = await repo.list()

    total = len(all_items)
    items = all_items[skip : skip + limit]
    return DictadoListResponse(
        items=[DictadoResponse.model_validate(d) for d in items],
        total=total,
    )


@router.post(
    "",
    response_model=DictadoResponse,
    status_code=201,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def create_dictado(
    body: DictadoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new dictado. Validates materia and carrera are active."""
    repo = DictadoRepository(session=db, tenant_id=current_user.tenant_id)

    # Validate materia exists and is active
    materia_query = (
        select(Materia)
        .where(Materia.id == body.materia_id)
        .where(Materia.tenant_id == current_user.tenant_id)
    )
    result = await db.execute(materia_query)
    materia = result.scalar_one_or_none()
    if materia is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada")
    if materia.estado != "activa":
        raise HTTPException(status_code=400, detail="La materia está inactiva")

    # Validate carrera exists and is active
    carrera_query = (
        select(Carrera)
        .where(Carrera.id == body.carrera_id)
        .where(Carrera.tenant_id == current_user.tenant_id)
    )
    result = await db.execute(carrera_query)
    carrera = result.scalar_one_or_none()
    if carrera is None:
        raise HTTPException(status_code=404, detail="Carrera no encontrada")
    if carrera.estado != "activa":
        raise HTTPException(status_code=400, detail="La carrera está inactiva")

    # Check unique combination (materia_id, carrera_id, cohorte_id)
    existing = await db.execute(
        select(Dictado.id)
        .where(Dictado.tenant_id == current_user.tenant_id)
        .where(Dictado.materia_id == body.materia_id)
        .where(Dictado.carrera_id == body.carrera_id)
        .where(Dictado.cohorte_id == body.cohorte_id)
        .where(Dictado.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Ya existe un dictado para esa materia, carrera y cohorte")

    instance = await repo.create(
        materia_id=body.materia_id,
        carrera_id=body.carrera_id,
        cohorte_id=body.cohorte_id,
    )
    return DictadoResponse.model_validate(instance)


@router.get(
    "/{dictado_id}",
    response_model=DictadoResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def get_dictado(
    dictado_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a dictado by ID."""
    repo = DictadoRepository(session=db, tenant_id=current_user.tenant_id)
    instance = await repo.get(dictado_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Dictado no encontrado")
    return DictadoResponse.model_validate(instance)


@router.put(
    "/{dictado_id}",
    response_model=DictadoResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def update_dictado(
    dictado_id: uuid.UUID,
    body: DictadoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a dictado (mainly closing by setting estado)."""
    repo = DictadoRepository(session=db, tenant_id=current_user.tenant_id)

    update_kwargs = body.model_dump(exclude_unset=True)
    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    instance = await repo.update(dictado_id, **update_kwargs)
    if instance is None:
        raise HTTPException(status_code=404, detail="Dictado no encontrado")
    return DictadoResponse.model_validate(instance)


@router.delete(
    "/{dictado_id}",
    status_code=204,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def delete_dictado(
    dictado_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a dictado."""
    repo = DictadoRepository(session=db, tenant_id=current_user.tenant_id)
    deleted = await repo.soft_delete(dictado_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dictado no encontrado")
    return None
