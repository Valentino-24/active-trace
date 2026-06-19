"""Comunicaciones router — preview, enqueue, approve, and track communications.

Endpoints:
- POST /api/comunicaciones/preview — preview templates (F3.1, RN-16)
- POST /api/comunicaciones/enviar — enqueue batch (F3.2)
- GET  /api/comunicaciones/lotes — list batches
- GET  /api/comunicaciones/lotes/{lote_id} — batch detail
- POST /api/comunicaciones/aprobar/lote/{lote_id} — batch approval (F3.3)
- POST /api/comunicaciones/aprobar/{comunicacion_id} — individual approval
- POST /api/comunicaciones/cancelar/{lote_id} — cancel batch
- GET  /api/comunicaciones/estadisticas — stats by materia
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.asignacion import Asignacion
from app.models.materia import Materia
from app.models.rbac import UserRole as UserRoleModel
from app.models.user import User
from app.schemas.comunicaciones import (
    AprobarRequest,
    ComunicacionResponse,
    EnviarRequest,
    EstadisticasResponse,
    LoteResponse,
    PreviewRequest,
    PreviewResponse,
)
from app.services.comunicacion_service import ComunicacionService

router = APIRouter(tags=["comunicaciones"])


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_profesor_asignacion_ids(
    db: AsyncSession,
    current_user: User,
) -> list[uuid.UUID] | None:
    """Get asignacion_ids for a PROFESOR-only user.

    Returns None if the user is COORDINADOR or ADMIN (no scope restriction).
    Returns empty list if PROFESOR has no asignaciones.
    """
    role_stmt = select(UserRoleModel).where(
        UserRoleModel.user_id == current_user.id,
        UserRoleModel.tenant_id == current_user.tenant_id,
        UserRoleModel.deleted_at.is_(None),
    ).options(joinedload(UserRoleModel.role))
    role_result = await db.execute(role_stmt)
    role_codes = {ur.role.codigo for ur in role_result.scalars().all()}

    is_profesor_only = (
        "PROFESOR" in role_codes
        and "COORDINADOR" not in role_codes
        and "ADMIN" not in role_codes
    )

    if not is_profesor_only:
        return None  # No restriction

    stmt = select(Asignacion.id).where(
        Asignacion.tenant_id == current_user.tenant_id,
        Asignacion.usuario_id == current_user.id,
        Asignacion.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def _verify_materia(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    materia_id: uuid.UUID,
) -> None:
    """Verify that materia exists and belongs to the tenant."""
    stmt = select(Materia).where(
        Materia.id == materia_id,
        Materia.tenant_id == tenant_id,
        Materia.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"Materia {materia_id} no encontrada en el tenant",
        )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/api/comunicaciones/preview",
    response_model=PreviewResponse,
    dependencies=[Depends(require_permission("comunicacion:enviar"))],
)
async def preview_comunicacion(
    body: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render templates for each recipient without persisting.

    Supported variables: ${nombre}, ${apellido}, ${materia},
    ${comision}, ${nombre_profesor}. Unknown variables are left as-is.
    """
    await _verify_materia(db, current_user.tenant_id, body.materia_id)

    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.preview(
        materia_id=body.materia_id,
        asunto_template=body.asunto_template,
        cuerpo_template=body.cuerpo_template,
        destinatarios=body.destinatarios,
    )


@router.post(
    "/api/comunicaciones/enviar",
    response_model=LoteResponse,
    status_code=201,
    dependencies=[Depends(require_permission("comunicacion:enviar"))],
)
async def enviar_comunicacion(
    body: EnviarRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue a batch of communications.

    Creates Comunicacion records in Pendiente state for each recipient
    from the active padron version of the materia. Grouped by lote_id.
    """
    await _verify_materia(db, current_user.tenant_id, body.materia_id)

    profesor_ids = await _get_profesor_asignacion_ids(db, current_user)

    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.enviar(
        materia_id=body.materia_id,
        asunto_template=body.asunto_template,
        cuerpo_template=body.cuerpo_template,
        requiere_aprobacion=body.requiere_aprobacion,
        profesor_asignacion_ids=profesor_ids,
    )


@router.get(
    "/api/comunicaciones/lotes",
    dependencies=[Depends(require_permission("comunicacion:enviar"))],
)
async def list_lotes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all communication batches (placeholder — returns recent)."""
    from app.models.comunicacion import Comunicacion

    stmt = (
        select(Comunicacion.lote_id, Comunicacion.created_at)
        .where(Comunicacion.tenant_id == current_user.tenant_id)
        .where(Comunicacion.deleted_at.is_(None))
        .distinct(Comunicacion.lote_id)
        .order_by(Comunicacion.lote_id, Comunicacion.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    lotes = []
    seen = set()
    for row in result.fetchall():
        lid = row[0]
        if lid and lid not in seen:
            seen.add(lid)
            lotes.append({"lote_id": str(lid), "created_at": row[1].isoformat() if row[1] else None})
    return {"items": lotes, "total": len(lotes)}


@router.get(
    "/api/comunicaciones/lotes/{lote_id}",
    dependencies=[Depends(require_permission("comunicacion:enviar"))],
)
async def get_lote_detail(
    lote_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details of all messages in a batch."""
    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.get_estado_lote(lote_id)


@router.post(
    "/api/comunicaciones/aprobar/lote/{lote_id}",
    response_model=LoteResponse,
    dependencies=[Depends(require_permission("comunicacion:aprobar"))],
)
async def aprobar_lote(
    lote_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve all pending messages in a batch → Enviando."""
    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.aprobar_lote(lote_id)


@router.post(
    "/api/comunicaciones/aprobar/{comunicacion_id}",
    response_model=ComunicacionResponse,
    dependencies=[Depends(require_permission("comunicacion:aprobar"))],
)
async def aprobar_individual(
    comunicacion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a single pending message → Enviando."""
    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.aprobar_individual(comunicacion_id)


@router.post(
    "/api/comunicaciones/cancelar/{lote_id}",
    response_model=LoteResponse,
    dependencies=[Depends(require_permission("comunicacion:aprobar"))],
)
async def cancelar_lote(
    lote_id: uuid.UUID,
    body: AprobarRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel all pending messages in a batch → Cancelado."""
    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.cancelar_lote(lote_id)


@router.get(
    "/api/comunicaciones/estadisticas",
    response_model=EstadisticasResponse,
    dependencies=[Depends(require_permission("comunicacion:enviar"))],
)
async def get_estadisticas(
    materia_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get communication counts by estado for a materia."""
    await _verify_materia(db, current_user.tenant_id, materia_id)

    service = ComunicacionService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.get_estadisticas(materia_id)
