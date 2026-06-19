"""Cohortes admin router — CRUD for cohorts within a carrera."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte

from app.models.user import User
from app.repositories.cohorte_repository import CohorteRepository
from app.schemas.cohorte import (
    CohorteCreate,
    CohorteListResponse,
    CohorteResponse,
    CohorteUpdate,
)

router = APIRouter(tags=["admin"])


@router.get(
    "",
    response_model=CohorteListResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def list_cohortes(
    carrera_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List cohortes for the current tenant, optionally filtered by carrera."""
    repo = CohorteRepository(session=db, tenant_id=current_user.tenant_id)

    if carrera_id is not None:
        all_items = await repo.list_by_carrera(carrera_id)
    else:
        all_items = await repo.list()

    total = len(all_items)
    items = all_items[skip : skip + limit]
    return CohorteListResponse(
        items=[CohorteResponse.model_validate(c) for c in items],
        total=total,
    )


@router.post(
    "",
    response_model=CohorteResponse,
    status_code=201,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def create_cohorte(
    body: CohorteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new cohorte. Validates that the carrera exists and is active."""
    repo = CohorteRepository(session=db, tenant_id=current_user.tenant_id)

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

    # Check unique nombre within (tenant, carrera)
    existing = await db.execute(
        select(Cohorte.id)
        .where(Cohorte.tenant_id == current_user.tenant_id)
        .where(Cohorte.carrera_id == body.carrera_id)
        .where(Cohorte.nombre == body.nombre)
        .where(Cohorte.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Ya existe una cohorte con ese nombre en esta carrera")

    instance = await repo.create(
        carrera_id=body.carrera_id,
        nombre=body.nombre,
        anio=body.anio,
        vig_desde=body.vig_desde,
        vig_hasta=body.vig_hasta,
    )
    return CohorteResponse.model_validate(instance)


@router.get(
    "/{cohorte_id}",
    response_model=CohorteResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def get_cohorte(
    cohorte_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a cohorte by ID."""
    repo = CohorteRepository(session=db, tenant_id=current_user.tenant_id)
    instance = await repo.get(cohorte_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Cohorte no encontrada")
    return CohorteResponse.model_validate(instance)


@router.put(
    "/{cohorte_id}",
    response_model=CohorteResponse,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def update_cohorte(
    cohorte_id: uuid.UUID,
    body: CohorteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a cohorte. Setting vig_hasta automatically changes estado."""
    repo = CohorteRepository(session=db, tenant_id=current_user.tenant_id)

    update_kwargs = body.model_dump(exclude_unset=True)
    if not update_kwargs:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    # If vig_hasta is being set, also set estado to inactiva per business rule
    if "vig_hasta" in update_kwargs and update_kwargs["vig_hasta"] is not None:
        update_kwargs["estado"] = "inactiva"

    instance = await repo.update(cohorte_id, **update_kwargs)
    if instance is None:
        raise HTTPException(status_code=404, detail="Cohorte no encontrada")
    return CohorteResponse.model_validate(instance)


@router.delete(
    "/{cohorte_id}",
    status_code=204,
    dependencies=[Depends(require_permission("estructura:gestionar"))],
)
async def delete_cohorte(
    cohorte_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a cohorte."""
    repo = CohorteRepository(session=db, tenant_id=current_user.tenant_id)
    deleted = await repo.soft_delete(cohorte_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cohorte no encontrada")
    return None
