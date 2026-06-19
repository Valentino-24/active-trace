"""Asignaciones router — manage user-role-context assignments.

Endpoints:
- GET /api/asignaciones — list assignments with filters
- POST /api/asignaciones — create an assignment
- DELETE /api/asignaciones/{id} — revoke (set hasta=today)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.repositories.asignacion_repository import AsignacionRepository
from app.schemas.asignacion import (
    AsignacionCreate,
    AsignacionListResponse,
    AsignacionResponse,
)

router = APIRouter(tags=["asignaciones"])


@router.get(
    "",
    response_model=AsignacionListResponse,
    dependencies=[Depends(require_permission("equipos:asignar"))],
)
async def list_asignaciones(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    usuario_id: uuid.UUID | None = Query(default=None),
    materia_id: uuid.UUID | None = Query(default=None),
    rol: str | None = Query(default=None),
    incluir_vencidas: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List asignaciones for the current tenant with optional filters."""
    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    asignaciones, total = await repo.list_asignaciones(
        skip=skip,
        limit=limit,
        usuario_id=usuario_id,
        materia_id=materia_id,
        rol=rol,
        incluir_vencidas=incluir_vencidas,
    )

    items = [AsignacionResponse.model_validate(a) for a in asignaciones]
    return AsignacionListResponse(items=items, total=total)


@router.post(
    "",
    response_model=AsignacionResponse,
    status_code=201,
    dependencies=[Depends(require_permission("equipos:asignar"))],
)
async def create_asignacion(
    body: AsignacionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new asignacion."""
    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    create_kwargs = body.model_dump()
    instance = await repo.create(**create_kwargs)
    return AsignacionResponse.model_validate(instance)


@router.delete(
    "/{asignacion_id}",
    response_model=AsignacionResponse,
    dependencies=[Depends(require_permission("equipos:revocar"))],
)
async def revoke_asignacion(
    asignacion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke an asignacion by setting hasta = today."""
    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    instance = await repo.revoke(asignacion_id)
    if instance is None:
        raise HTTPException(
            status_code=404, detail="Asignación no encontrada"
        )
    return AsignacionResponse.model_validate(instance)
