"""Guardias router — API endpoints for guardia management.

Endpoints:
- POST /api/guardias — register a guardia (F6.6)
- GET  /api/guardias — list guardias with filters
- GET  /api/guardias/export — export to CSV
- PATCH /api/guardias/{id} — update guardia

All endpoints guarded by guardias:gestionar permission.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.guardias import (
    GuardiaCrearRequest,
    GuardiaListResponse,
    GuardiaResponse,
    GuardiaUpdateRequest,
)
from app.services.guardia_service import GuardiaService

router = APIRouter(tags=["guardias"])


@router.post(
    "/api/guardias",
    response_model=GuardiaResponse,
    status_code=201,
    dependencies=[Depends(require_permission("guardias:gestionar"))],
)
async def crear_guardia(
    body: GuardiaCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new guardia record.

    TUTOR or PROFESOR can register their own guardias.
    State defaults to Pendiente.
    """
    service = GuardiaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.crear(body)


@router.get(
    "/api/guardias",
    response_model=GuardiaListResponse,
    dependencies=[Depends(require_permission("guardias:gestionar"))],
)
async def listar_guardias(
    materia_id: uuid.UUID | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    estado: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List guardias with optional filters.

    Scope: PROFESOR/TUTOR sees only their own guardias (by asignacion).
    COORDINADOR/ADMIN sees all in the tenant.
    """
    service = GuardiaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar(
        materia_id=materia_id, desde=desde, hasta=hasta, estado=estado,
    )


@router.get(
    "/api/guardias/export",
    dependencies=[Depends(require_permission("guardias:gestionar"))],
)
async def exportar_guardias(
    materia_id: uuid.UUID | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    estado: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export guardias to CSV.

    Same filters as list. Returns Content-Type: text/csv with attachment.
    """
    service = GuardiaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    csv_str = await service.exportar_csv(
        materia_id=materia_id, desde=desde, hasta=hasta, estado=estado,
    )
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=guardias.csv"},
    )


@router.patch(
    "/api/guardias/{guardia_id}",
    response_model=GuardiaResponse,
    dependencies=[Depends(require_permission("guardias:gestionar"))],
)
async def actualizar_guardia(
    guardia_id: uuid.UUID,
    body: GuardiaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update estado and/or comentarios of a guardia."""
    service = GuardiaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.actualizar(guardia_id, body)
