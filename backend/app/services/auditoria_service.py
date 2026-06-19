"""Auditoria service — analytics and scope logic."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.auditoria import (
    AccionesPorDiaResponse, AccionesPorDiaItem,
    MetricasDocenteResponse, MetricaDocenteItem,
    AuditLogListResponse, AuditLogItem,
)


class AuditoriaService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._repo = AuditLogRepository(session=db, tenant_id=tenant_id)

    def _is_admin(self) -> bool:
        roles = getattr(self._current_user, "roles", [])
        if not isinstance(roles, list):
            roles = [roles] if roles else []
        for ur in roles:
            role = getattr(ur, "role", None)
            if role is not None and role.codigo == "ADMIN":
                return True
        return False

    def _scope_actor_id(self) -> uuid.UUID | None:
        if self._is_admin():
            return None
        return self._current_user.id

    async def acciones_por_dia(self, desde: date | None = None,
                                hasta: date | None = None) -> AccionesPorDiaResponse:
        data = await self._repo.acciones_por_dia(
            desde=desde, hasta=hasta, actor_id=self._scope_actor_id(),
        )
        items = [AccionesPorDiaItem(**d) for d in data]
        return AccionesPorDiaResponse(items=items, total=len(items))

    async def metricas_por_docente(self) -> MetricasDocenteResponse:
        data = await self._repo.metricas_por_docente(actor_id=self._scope_actor_id())
        items = [MetricaDocenteItem(**d) for d in data]
        return MetricasDocenteResponse(items=items, total=len(items))

    async def recientes(self, limit: int = 200) -> AuditLogListResponse:
        if self._scope_actor_id():
            all_items = await self._repo.list_con_filtros(
                usuario_id=self._scope_actor_id(),
            )
            all_items = all_items[:limit]
        else:
            all_items = await self._repo.recientes(limit=limit)
        items = [self._to_item(al) for al in all_items]
        return AuditLogListResponse(items=items, total=len(items))

    async def list_con_filtros(
        self, fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        materia_id: uuid.UUID | None = None,
        usuario_id: uuid.UUID | None = None,
        accion: str | None = None,
    ) -> AuditLogListResponse:
        scope_id = self._scope_actor_id()
        effective_usuario = scope_id or usuario_id
        all_items = await self._repo.list_con_filtros(
            fecha_desde=fecha_desde, fecha_hasta=fecha_hasta,
            materia_id=materia_id, usuario_id=effective_usuario, accion=accion,
        )
        items = [self._to_item(al) for al in all_items]
        return AuditLogListResponse(items=items, total=len(items))

    def _to_item(self, al) -> AuditLogItem:
        return AuditLogItem(
            id=al.id, actor_id=al.actor_id, accion=al.accion,
            fecha_hora=al.fecha_hora, materia_id=al.materia_id,
            filas_afectadas=al.filas_afectadas, detalle=al.detalle,
            ip=al.ip,
        )
