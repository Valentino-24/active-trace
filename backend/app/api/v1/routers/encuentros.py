"""Encuentros router — API endpoints for slot and instance management.

Endpoints:
- POST /api/encuentros/slots — create slot + generate instances (F6.1/F6.2)
- PATCH /api/encuentros/instancias/{id} — update instance (F6.3)
- GET  /api/encuentros/instancias — list instances
- GET  /api/encuentros/slots — list slots
- GET  /api/encuentros/instancias/{id}/html — HTML block (F6.4)
- GET  /api/encuentros/admin — admin transversal view (F6.5)

All endpoints guarded by encuentros:gestionar permission.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.encuentros import (
    HtmlResponse,
    InstanciaListResponse,
    InstanciaResponse,
    InstanciaUpdateRequest,
    SlotConInstanciasResponse,
    SlotCrearRequest,
    SlotListResponse,
)
from app.services.encuentro_service import EncuentroService

router = APIRouter(tags=["encuentros"])


@router.post(
    "/api/encuentros/slots",
    response_model=SlotConInstanciasResponse,
    status_code=201,
    dependencies=[Depends(require_permission("encuentros:gestionar"))],
)
async def crear_slot(
    body: SlotCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a slot and generate its instances synchronously.

    Two modes (RN-13):
        - Recurrente: cant_semanas > 0
        - Fecha única: cant_semanas = 0, fecha_unica set
    """
    service = EncuentroService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.crear_slot(body)


@router.patch(
    "/api/encuentros/instancias/{instancia_id}",
    response_model=InstanciaResponse,
    dependencies=[Depends(require_permission("encuentros:gestionar"))],
)
async def editar_instancia(
    instancia_id: uuid.UUID,
    body: InstanciaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update estado, meet_url, video_url, or comentario of an instance.

    Any state → any state per RN-14. Does not affect slot or other instances.
    """
    service = EncuentroService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.editar_instancia(instancia_id, body)


@router.get(
    "/api/encuentros/instancias",
    response_model=InstanciaListResponse,
    dependencies=[Depends(require_permission("encuentros:gestionar"))],
)
async def listar_instancias(
    materia_id: uuid.UUID | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List instances with optional materia and date range filters.

    Scope: PROFESOR/TUTOR sees only their assigned materias.
    COORDINADOR/ADMIN sees all.
    """
    service = EncuentroService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_instancias(
        materia_id=materia_id, desde=desde, hasta=hasta,
    )


@router.get(
    "/api/encuentros/slots",
    response_model=SlotListResponse,
    dependencies=[Depends(require_permission("encuentros:gestionar"))],
)
async def listar_slots(
    materia_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List slots with optional materia filter.

    Scope: PROFESOR/TUTOR sees only their assigned materias.
    """
    service = EncuentroService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_slots(materia_id=materia_id)


@router.get(
    "/api/encuentros/instancias/{instancia_id}/html",
    response_model=HtmlResponse,
    dependencies=[Depends(require_permission("encuentros:gestionar"))],
)
async def generar_html(
    instancia_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an HTML block with encuentro data for LMS embedding (F6.4).

    Returns server-generated HTML with escaped URLs. The user copies this
    into the LMS.
    """
    service = EncuentroService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.generar_html(instancia_id)


@router.get(
    "/api/encuentros/admin",
    response_model=InstanciaListResponse,
    dependencies=[Depends(require_permission("encuentros:gestionar"))],
)
async def vista_admin(
    materia_id: uuid.UUID | None = Query(default=None),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    estado: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin transversal view — all encuentros in the tenant (F6.5).

    Intended for COORDINADOR/ADMIN roles. PROFESOR/TUTOR gets scoped
    results (same as regular list).
    """
    service = EncuentroService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.vista_admin(
        materia_id=materia_id, desde=desde, hasta=hasta, estado=estado,
    )
