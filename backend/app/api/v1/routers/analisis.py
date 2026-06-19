"""Analisis router — analytical endpoints and reports.

Endpoints:
- GET /api/analisis/atrasados — list atrasados (F2.2)
- GET /api/analisis/ranking — ranking (F2.3)
- GET /api/analisis/reportes-rapidos — consolidated metrics (F2.4)
- GET /api/analisis/notas-finales — final grades (F2.5)
- GET /api/analisis/exportar-sin-corregir — CSV export (F2.6)
- GET /api/analisis/monitor-general — general monitor (F2.7)
- GET /api/analisis/monitor-seguimiento — seguimiento (F2.8/F2.9)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.rbac import UserRole as UserRoleModel
from app.models.user import User
from app.schemas.analisis import (
    AtrasadosResponse,
    MonitorGeneralResponse,
    MonitorSeguimientoResponse,
    NotasFinalesResponse,
    RankingResponse,
    ReporteRapidoResponse,
)
from app.services.analisis_service import AnalisisService

router = APIRouter(tags=["analisis"])


# ── Helpers (duplicated from calificaciones.py per checkpoint decision) ─────


async def _get_profesor_asignacion_ids(
    db: AsyncSession,
    current_user: User,
) -> tuple[list[uuid.UUID], bool]:
    """Get asignacion_ids for a PROFESOR/TUTOR-only user.

    Returns:
        Tuple of (asignacion_ids, is_restricted).
        - If COORDINADOR/ADMIN: ([], False) — no scope restriction.
        - If PROFESOR/TUTOR with asignaciones: ([...], True).
        - If PROFESOR/TUTOR with no asignaciones: ([], True) → caller
          should return 403.

    NOTE: Duplicated from calificaciones.py per design decision to avoid
    refactoring C-10 code. If this needs to be shared, extract to
    app.core.permissions.
    """
    role_stmt = select(UserRoleModel).where(
        UserRoleModel.user_id == current_user.id,
        UserRoleModel.tenant_id == current_user.tenant_id,
        UserRoleModel.deleted_at.is_(None),
    ).options(joinedload(UserRoleModel.role))
    role_result = await db.execute(role_stmt)
    role_codes = {ur.role.codigo for ur in role_result.scalars().all()}

    is_restricted = (
        "PROFESOR" in role_codes or "TUTOR" in role_codes
    ) and "COORDINADOR" not in role_codes and "ADMIN" not in role_codes

    if not is_restricted:
        return [], False  # No restriction — COORD/ADMIN

    from app.models.asignacion import Asignacion

    stmt = select(Asignacion.id).where(
        Asignacion.tenant_id == current_user.tenant_id,
        Asignacion.usuario_id == current_user.id,
        Asignacion.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    ids = [row[0] for row in result.fetchall()]
    return ids, True


async def _verify_materia_cohorte(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    materia_id: uuid.UUID,
    cohorte_id: uuid.UUID,
) -> None:
    """Verify that materia and cohorte exist and belong to the tenant."""
    from app.models.cohorte import Cohorte
    from app.models.materia import Materia

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


# ── GET /api/analisis/atrasados (F2.2 — R-ANA-01) ─────────────────────────


@router.get(
    "/api/analisis/atrasados",
    response_model=AtrasadosResponse,
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def listar_atrasados(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List students who are atrasado for a materia+cohorte.

    PROFESOR/TUTOR only see students from their own teaching assignments.
    COORDINADOR/ADMIN see all students.
    """
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    asig_ids, is_restricted = await _get_profesor_asignacion_ids(db, current_user)
    if is_restricted and not asig_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
    return await service.listar_atrasados(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        asignacion_ids=asig_ids or None,
    )


# ── GET /api/analisis/ranking (F2.3 — R-ANA-02) ───────────────────────────


@router.get(
    "/api/analisis/ranking",
    response_model=RankingResponse,
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def get_ranking(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get ranking of students by approved activities.

    Only includes students with ≥1 approved activity (RN-09).
    Scope: PROFESOR/TUTOR own asignacion, COORD/ADMIN global.
    """
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    asig_ids, is_restricted = await _get_profesor_asignacion_ids(db, current_user)
    if is_restricted and not asig_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
    return await service.get_ranking(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        asignacion_ids=asig_ids or None,
    )


# ── GET /api/analisis/reportes-rapidos (F2.4 — R-ANA-03) ──────────────────


@router.get(
    "/api/analisis/reportes-rapidos",
    response_model=ReporteRapidoResponse,
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def get_reportes_rapidos(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get consolidated metrics for a materia+cohorte."""
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    asig_ids, is_restricted = await _get_profesor_asignacion_ids(db, current_user)
    if is_restricted and not asig_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
    return await service.get_reportes_rapidos(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        asignacion_ids=asig_ids or None,
    )


# ── GET /api/analisis/notas-finales (F2.5 — R-ANA-04) ─────────────────────


@router.get(
    "/api/analisis/notas-finales",
    response_model=NotasFinalesResponse,
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def get_notas_finales(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get final grade averages per student."""
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    asig_ids, is_restricted = await _get_profesor_asignacion_ids(db, current_user)
    if is_restricted and not asig_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
    return await service.get_notas_finales(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        asignacion_ids=asig_ids or None,
    )


# ── GET /api/analisis/exportar-sin-corregir (F2.6 — R-ANA-05) ─────────────


@router.get(
    "/api/analisis/exportar-sin-corregir",
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def exportar_sin_corregir(
    materia_id: uuid.UUID = Query(...),
    cohorte_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export textual activities without grades as CSV.

    Returns a downloadable CSV file with BOM for Excel compatibility.
    Only includes textual activities (RN-08).
    """
    await _verify_materia_cohorte(db, current_user.tenant_id, materia_id, cohorte_id)

    asig_ids, is_restricted = await _get_profesor_asignacion_ids(db, current_user)
    if is_restricted and not asig_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
    return await service.exportar_sin_corregir(
        materia_id=materia_id,
        cohorte_id=cohorte_id,
        asignacion_ids=asig_ids or None,
    )


# ── GET /api/analisis/monitor-general (F2.7 — R-ANA-06) ───────────────────


@router.get(
    "/api/analisis/monitor-general",
    response_model=MonitorGeneralResponse,
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def get_monitor_general(
    materia_id: uuid.UUID | None = Query(default=None),
    comision: str | None = Query(default=None),
    regional: str | None = Query(default=None),
    q: str | None = Query(default=None, alias="q"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get general monitor view with optional filters.

    Only available for COORDINADOR and ADMIN roles.
    PROFESOR gets 403 even with atrasados:ver permission.
    """
    # Inline role check: only COORD/ADMIN can access
    role_stmt = select(UserRoleModel).where(
        UserRoleModel.user_id == current_user.id,
        UserRoleModel.tenant_id == current_user.tenant_id,
        UserRoleModel.deleted_at.is_(None),
    ).options(joinedload(UserRoleModel.role))
    role_result = await db.execute(role_stmt)
    role_codes = {ur.role.codigo for ur in role_result.scalars().all()}

    if not ("COORDINADOR" in role_codes or "ADMIN" in role_codes):
        raise HTTPException(status_code=403, detail="Forbidden")

    service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
    return await service.monitor_general(
        materia_id=materia_id,
        comision=comision,
        regional=regional,
        q=q,
        skip=skip,
        limit=limit,
    )


# ── GET /api/analisis/monitor-seguimiento (F2.8/F2.9 — R-ANA-07/08) ───────


@router.get(
    "/api/analisis/monitor-seguimiento",
    response_model=MonitorSeguimientoResponse,
    dependencies=[Depends(require_permission("atrasados:ver"))],
)
async def get_monitor_seguimiento(
    materia_id: uuid.UUID | None = Query(default=None),
    alumno_id: uuid.UUID | None = Query(default=None),
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed seguimiento data.

    PROFESOR/TUTOR: scoped to own asignaciones, desde/hasta ignored.
    COORDINADOR/ADMIN: global scope, desde/hasta filters applied.
    """
    asig_ids, is_restricted = await _get_profesor_asignacion_ids(db, current_user)
    if is_restricted and not asig_ids:
        raise HTTPException(status_code=403, detail="Forbidden")

    # COORD/ADMIN have is_restricted=False → asig_ids=[], apply fechas
    is_coord_or_admin = not is_restricted

    # Validate date range for COORD/ADMIN
    if is_coord_or_admin and desde is not None and hasta is not None:
        if desde > hasta:
            raise HTTPException(
                status_code=422,
                detail="desde debe ser anterior o igual a hasta",
            )

    if is_coord_or_admin:
        # COORD/ADMIN: unrestricted scope, apply date filters
        service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
        return await service.monitor_seguimiento(
            materia_id=materia_id,
            alumno_id=alumno_id,
            asignacion_ids=None,
            desde=desde,
            hasta=hasta,
        )
    else:
        # PROFESOR/TUTOR: scoped, ignore desde/hasta
        service = AnalisisService(db=db, tenant_id=current_user.tenant_id)
        return await service.monitor_seguimiento(
            materia_id=materia_id,
            alumno_id=alumno_id,
            asignacion_ids=asig_ids,
            desde=None,
            hasta=None,
        )
