"""Programas y Fechas Academicas router.

Endpoints (guard: estructura:gestionar):
    POST   /api/programas
    GET    /api/programas
    PATCH  /api/programas/{id}
    DELETE /api/programas/{id}
    POST   /api/fechas-academicas
    GET    /api/fechas-academicas
    PATCH  /api/fechas-academicas/{id}
    DELETE /api/fechas-academicas/{id}
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.programas_fechas import (
    ProgramaCrearRequest, ProgramaUpdateRequest, ProgramaResponse, ProgramaListResponse,
    FechaCrearRequest, FechaUpdateRequest, FechaResponse, FechaListResponse,
)
from app.services.programa_fecha_service import ProgramaFechaService

router = APIRouter(tags=["programas-fechas"])

_GUARD = Depends(require_permission("estructura:gestionar"))


# ── Programas ─────────────────────────────────────────────────────────────


@router.post("/api/programas", response_model=ProgramaResponse, status_code=201,
             dependencies=[_GUARD])
async def crear_programa(
    body: ProgramaCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.crear_programa(body)


@router.get("/api/programas", response_model=ProgramaListResponse, dependencies=[_GUARD])
async def listar_programas(
    materia_id: uuid.UUID | None = Query(default=None),
    cohorte_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_programas(materia_id=materia_id, cohorte_id=cohorte_id)


@router.patch("/api/programas/{programa_id}", response_model=ProgramaResponse,
              dependencies=[_GUARD])
async def actualizar_programa(
    programa_id: uuid.UUID,
    body: ProgramaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.actualizar_programa(programa_id, body)


@router.delete("/api/programas/{programa_id}", status_code=200, dependencies=[_GUARD])
async def eliminar_programa(
    programa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    await svc.eliminar_programa(programa_id)
    return {"detail": "Programa eliminado"}


# ── Fechas Academicas ──────────────────────────────────────────────────────


@router.post("/api/fechas-academicas", response_model=FechaResponse, status_code=201,
             dependencies=[_GUARD])
async def crear_fecha(
    body: FechaCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.crear_fecha(body)


@router.get("/api/fechas-academicas", response_model=FechaListResponse, dependencies=[_GUARD])
async def listar_fechas(
    materia_id: uuid.UUID | None = Query(default=None),
    cohorte_id: uuid.UUID | None = Query(default=None),
    tipo: str | None = Query(default=None),
    periodo: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_fechas(materia_id=materia_id, cohorte_id=cohorte_id,
                                    tipo=tipo, periodo=periodo)


@router.patch("/api/fechas-academicas/{fecha_id}", response_model=FechaResponse,
              dependencies=[_GUARD])
async def actualizar_fecha(
    fecha_id: uuid.UUID,
    body: FechaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.actualizar_fecha(fecha_id, body)


@router.delete("/api/fechas-academicas/{fecha_id}", status_code=200, dependencies=[_GUARD])
async def eliminar_fecha(
    fecha_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProgramaFechaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    await svc.eliminar_fecha(fecha_id)
    return {"detail": "Fecha eliminada"}
