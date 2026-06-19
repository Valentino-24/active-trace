"""Avisos router — API endpoints for institutional notice board.

Endpoints de gestión (guard: avisos:publicar):
    POST   /api/avisos            — create a notice
    PATCH  /api/avisos/{id}       — update a notice
    DELETE /api/avisos/{id}       — soft-delete a notice
    GET    /api/avisos            — list with acknowledgment counters
    GET    /api/avisos/{id}/acks  — list acknowledgments

Endpoints de usuario (sin permiso especial):
    GET    /api/avisos/mis-avisos — visible notices for current user
    POST   /api/avisos/{id}/ack   — acknowledge a notice
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.avisos import (
    AckResponse,
    AcksListResponse,
    AvisoCrearRequest,
    AvisoListResponse,
    AvisoResponse,
    AvisoUpdateRequest,
    MisAvisosResponse,
)
from app.services.aviso_service import AvisoService

router = APIRouter(tags=["avisos"])


# ═══════════════════════════════════════════════════════════════════════════════
# Gestión (guard: avisos:publicar)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post(
    "/api/avisos",
    response_model=AvisoResponse,
    status_code=201,
    dependencies=[Depends(require_permission("avisos:publicar"))],
)
async def crear_aviso(
    body: AvisoCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new institutional notice.

    Only COORDINADOR/ADMIN with `avisos:publicar` permission can create notices.
    """
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.crear(body)


@router.patch(
    "/api/avisos/{aviso_id}",
    response_model=AvisoResponse,
    dependencies=[Depends(require_permission("avisos:publicar"))],
)
async def actualizar_aviso(
    aviso_id: uuid.UUID,
    body: AvisoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing notice.

    Only fields sent in the request body are updated (partial update).
    """
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.actualizar(aviso_id, body)


@router.delete(
    "/api/avisos/{aviso_id}",
    status_code=200,
    dependencies=[Depends(require_permission("avisos:publicar"))],
)
async def eliminar_aviso(
    aviso_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a notice.

    The notice remains in the database with deleted_at set.
    """
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    await service.eliminar(aviso_id)
    return {"detail": "Aviso eliminado"}


@router.get(
    "/api/avisos",
    response_model=AvisoListResponse,
    dependencies=[Depends(require_permission("avisos:publicar"))],
)
async def listar_avisos_gestion(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all non-deleted notices with acknowledgment counters."""
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_gestion()


@router.get(
    "/api/avisos/{aviso_id}/acks",
    response_model=AcksListResponse,
    dependencies=[Depends(require_permission("avisos:publicar"))],
)
async def listar_acks(
    aviso_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all acknowledgments for a specific notice."""
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_acks(aviso_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Usuario (sin permiso especial — cualquier autenticado)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/api/avisos/mis-avisos",
    response_model=MisAvisosResponse,
)
async def mis_avisos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active notices visible to the authenticated user.

    Applies audience scope (RN-20), validity window (RN-18),
    and read acknowledgment exclusion (RN-19).
    No special permission required — any authenticated user can call this.
    """
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_mis_avisos()


@router.post(
    "/api/avisos/{aviso_id}/ack",
    response_model=AckResponse,
    status_code=201,
)
async def ack_aviso(
    aviso_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge (confirm receipt of) a notice.

    No special permission required. Returns 409 if:
    - The notice does not require acknowledgment.
    - The user has already acknowledged this notice.
    """
    service = AvisoService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.ack(aviso_id)
