"""Auditoria router — analytics and audit log endpoints (read-only)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.auditoria import (
    AccionesPorDiaResponse, MetricasDocenteResponse, AuditLogListResponse,
)
from app.services.auditoria_service import AuditoriaService

router = APIRouter(tags=["auditoria"])
_GUARD = Depends(require_permission("auditoria:ver"))


@router.get("/api/auditoria/acciones-por-dia", response_model=AccionesPorDiaResponse,
            dependencies=[_GUARD])
async def acciones_por_dia(
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = AuditoriaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.acciones_por_dia(desde=desde, hasta=hasta)


@router.get("/api/auditoria/por-docente", response_model=MetricasDocenteResponse,
            dependencies=[_GUARD])
async def metricas_por_docente(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = AuditoriaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.metricas_por_docente()


@router.get("/api/auditoria/recientes", response_model=AuditLogListResponse,
            dependencies=[_GUARD])
async def recientes(
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = AuditoriaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.recientes(limit=limit)


@router.get("/api/auditoria/log", response_model=AuditLogListResponse,
            dependencies=[_GUARD])
async def log_auditoria(
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
    materia_id: uuid.UUID | None = Query(default=None),
    usuario_id: uuid.UUID | None = Query(default=None),
    accion: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = AuditoriaService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.list_con_filtros(
        fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
        materia_id=materia_id, usuario_id=usuario_id, accion=accion,
    )
