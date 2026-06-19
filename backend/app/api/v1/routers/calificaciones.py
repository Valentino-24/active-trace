"""Calificaciones router — grades and thresholds endpoints.

Endpoints:
- POST /api/calificaciones/preview — preview an LMS grade file
- POST /api/calificaciones/import — confirm and persist grade import
- POST /api/calificaciones/importar-finalizacion — detect ungraded submissions
- GET  /api/calificaciones — list grades with filters
- GET  /api/umbrales — list thresholds for a materia
- PUT  /api/umbrales/{id} — update a threshold
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.rbac import UserRole as UserRoleModel
from app.models.user import User
from app.schemas.calificacion import (
    CalificacionListResponse,
    CalificacionResponse,
    FinalizacionResponse,
    ImportRequest,
    ImportResponse,
    PreviewResponse,
)
from app.schemas.umbral import (
    UmbralListResponse,
    UmbralResponse,
    UmbralUpdateRequest,
)
from app.services.calificaciones_service import CalificacionesService
from app.services.umbral_service import UmbralService
from app.services.audit_service import log_action

router = APIRouter(tags=["calificaciones"])


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _verify_materia_cohorte(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    materia_id: uuid.UUID,
    cohorte_id: uuid.UUID,
) -> None:
    """Verify that materia and cohorte exist and belong to the tenant."""
    mat_stmt = select(Materia).where(
        Materia.id == materia_id,
        Materia.tenant_id == tenant_id,
        Materia.deleted_at.is_(None),
    )
    mat_result = await db.execute(mat_stmt)
    if mat_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"Materia {materia_id} no encontrada en el tenant",
        )

    coh_stmt = select(Cohorte).where(
        Cohorte.id == cohorte_id,
        Cohorte.tenant_id == tenant_id,
        Cohorte.deleted_at.is_(None),
    )
    coh_result = await db.execute(coh_stmt)
    if coh_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cohorte {cohorte_id} no encontrada en el tenant",
        )


async def _get_profesor_asignacion_ids(
    db: AsyncSession,
    current_user: User,
) -> list[uuid.UUID]:
    """Get asignacion_ids for a PROFESOR-only user.

    Returns empty list if the user is COORDINADOR or ADMIN (no scope restriction).
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
        return []  # No restriction

    from app.models.asignacion import Asignacion

    stmt = select(Asignacion.id).where(
        Asignacion.tenant_id == current_user.tenant_id,
        Asignacion.usuario_id == current_user.id,
        Asignacion.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.fetchall()]


def _get_asignacion_id(
    current_user: User,
    materia_id: uuid.UUID,
    cohorte_id: uuid.UUID,
) -> uuid.UUID | None:
    """Get the first matching asignacion_id for a PROFESOR user.

    Returns None if the user is COORDINADOR/ADMIN (no restriction).
    """
    # We'll look this up in the endpoint using _get_profesor_asignacion_ids
    # This is a placeholder utility kept for reference
    return None


# ── Endpoints: /api/calificaciones ──────────────────────────────────────────


@router.post(
    "/api/calificaciones/preview",
    response_model=PreviewResponse,
    dependencies=[Depends(require_permission("calificaciones:importar"))],
)
async def preview_calificaciones(
    archivo: UploadFile,
    materia_id: str = Query(...),
    cohorte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview an LMS grade file without persisting.

    Parses the uploaded .xlsx or .csv file, detects columns (RN-01/RN-02),
    and returns parsed rows with any errors per row.
    """
    mat_uuid = uuid.UUID(materia_id)
    coh_uuid = uuid.UUID(cohorte_id)

    await _verify_materia_cohorte(db, current_user.tenant_id, mat_uuid, coh_uuid)

    service = CalificacionesService(db=db, tenant_id=current_user.tenant_id)
    return await service.preview_import(
        file=archivo,
        materia_id=mat_uuid,
        cohorte_id=coh_uuid,
    )


@router.post(
    "/api/calificaciones/import",
    response_model=ImportResponse,
    status_code=201,
    dependencies=[Depends(require_permission("calificaciones:importar"))],
)
async def import_calificaciones(
    body: ImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm and persist a grade import.

    Matches students by email hash, resolves the effective threshold,
    computes aprobado, creates Calificacion records, and logs audit.
    """
    await _verify_materia_cohorte(
        db, current_user.tenant_id, body.materia_id, body.cohorte_id,
    )

    if not body.notas:
        raise HTTPException(
            status_code=400, detail="No se enviaron notas para importar",
        )

    if len(body.notas) > 10_000:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo 10.000 notas por import. Recibidas: {len(body.notas)}",
        )

    # Get asignacion_id for PROFESOR scope
    asig_ids = await _get_profesor_asignacion_ids(db, current_user)
    if asig_ids:
        # PROFESOR: use their first active asignacion for this materia
        from app.models.asignacion import Asignacion

        stmt = select(Asignacion.id).where(
            Asignacion.id.in_(asig_ids),
            Asignacion.materia_id == body.materia_id,
            Asignacion.cohorte_id == body.cohorte_id,
        )
        result = await db.execute(stmt)
        matching_asig = result.scalar_one_or_none()
        if matching_asig is None:
            raise HTTPException(
                status_code=403,
                detail="No tienes una asignación activa en esta materia/cohorte",
            )
        asignacion_id = matching_asig
    else:
        # For COORD/ADMIN, scope by current user's asignacion for this materia/cohorte.
        from app.models.asignacion import Asignacion

        stmt = select(Asignacion.id).where(
            Asignacion.tenant_id == current_user.tenant_id,
            Asignacion.usuario_id == current_user.id,
            Asignacion.materia_id == body.materia_id,
            Asignacion.cohorte_id == body.cohorte_id,
            Asignacion.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        asig = result.scalar_one_or_none()
        if asig is None:
            raise HTTPException(
                status_code=400,
                detail="No hay asignación activa para esta materia/cohorte",
            )
        asignacion_id = asig

    notas_data = [n.model_dump() for n in body.notas]
    service = CalificacionesService(db=db, tenant_id=current_user.tenant_id)
    return await service.importar_calificaciones(
        current_user=current_user,
        materia_id=body.materia_id,
        cohorte_id=body.cohorte_id,
        asignacion_id=asignacion_id,
        actividad_nombre=body.actividad_nombre,
        notas=notas_data,
        max_nota=body.max_nota,
    )


@router.post(
    "/api/calificaciones/importar-finalizacion",
    response_model=FinalizacionResponse,
    dependencies=[Depends(require_permission("calificaciones:importar"))],
)
async def importar_finalizacion(
    archivo: UploadFile,
    materia_id: str = Query(...),
    cohorte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a finalizacion report to detect ungraded submissions.

    Parses the file, identifies textual activities (RN-02), and
    returns students who have submissions without grades.
    """
    mat_uuid = uuid.UUID(materia_id)
    coh_uuid = uuid.UUID(cohorte_id)

    await _verify_materia_cohorte(db, current_user.tenant_id, mat_uuid, coh_uuid)

    service = CalificacionesService(db=db, tenant_id=current_user.tenant_id)
    return await service.importar_finalizacion(
        cohorte_id=coh_uuid,
        materia_id=mat_uuid,
        file=archivo,
    )


@router.get(
    "/api/calificaciones",
    response_model=CalificacionListResponse,
    dependencies=[Depends(require_permission("calificaciones:ver"))],
)
async def list_calificaciones(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List grade records with optional scope filtering.

    PROFESOR only sees grades from their own teaching assignments.
    COORDINADOR/ADMIN sees all grades for the materia/cohorte.
    """
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    # Scope: PROFESOR only sees their own asignacion
    asig_ids = await _get_profesor_asignacion_ids(db, current_user)
    asignacion_id = asig_ids[0] if len(asig_ids) == 1 else (asig_ids if asig_ids else None)

    service = CalificacionesService(db=db, tenant_id=current_user.tenant_id)
    calificaciones, total = await service.list_calificaciones(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        asignacion_id=asignacion_id,
        skip=skip,
        limit=limit,
    )

    items = [CalificacionResponse.model_validate(c) for c in calificaciones]
    return CalificacionListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


# ── Endpoints: /api/umbrales ────────────────────────────────────────────────


@router.get(
    "/api/umbrales",
    response_model=UmbralListResponse,
    dependencies=[Depends(require_permission("calificaciones:ver"))],
)
async def list_umbrales(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List thresholds for a given materia and cohorte.

    Returns both materia-wide defaults and assignment-specific thresholds.
    """
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    service = UmbralService(db=db, tenant_id=current_user.tenant_id)
    umbrales = await service.list_umbrales(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
    )

    items = [UmbralResponse.model_validate(u) for u in umbrales]
    return UmbralListResponse(items=items)


@router.put(
    "/api/umbrales/{umbral_id}",
    response_model=UmbralResponse,
    dependencies=[Depends(require_permission("calificaciones:importar"))],
)
async def update_umbral(
    umbral_id: uuid.UUID,
    body: UmbralUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a threshold configuration.

    PROFESOR can only update thresholds belonging to their own assignments.
    COORDINADOR/ADMIN can update any.
    At least one of umbral_pct or valores_aprobatorios must be provided.
    """
    if body.umbral_pct is None and body.valores_aprobatorios is None:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar al menos umbral_pct o valores_aprobatorios",
        )

    service = UmbralService(db=db, tenant_id=current_user.tenant_id)
    umbral = await service.update_umbral(
        umbral_id=umbral_id,
        data=body,
        current_user=current_user,
    )
    return UmbralResponse.model_validate(umbral)
