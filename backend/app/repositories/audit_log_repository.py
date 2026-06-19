"""AuditLog repository — append-only data access + analytics queries.

Only exposes create() and list() for writes.
Analytics: acciones_por_dia(), metricas_por_docente(), recientes(), list_con_filtros().
No update, delete, or soft-delete — AuditLog is immutable.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type, datetime
from typing import Sequence

from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Append-only repository for AuditLog.

    Only create and list are exposed; update, soft_delete are
    blocked at the application level. The Alembic migration also
    adds REVOKE UPDATE, DELETE at the database level.
    """

    _model_cls = AuditLog

    async def update(self, id: object = None, **kwargs: object):  # type: ignore[override]
        raise RuntimeError("AuditLog does not support update")

    async def soft_delete(self, id: object = None):  # type: ignore[override]
        raise RuntimeError("AuditLog does not support delete")

    # ── Analytics (read-only) ──────────────────────────────────────────────

    async def acciones_por_dia(
        self,
        desde: date_type | None = None,
        hasta: date_type | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                func.date(AuditLog.fecha_hora).label("fecha"),
                func.count(AuditLog.id).label("total"),
            )
            .where(AuditLog.tenant_id == self._tenant_id)
        )
        if desde:
            stmt = stmt.where(func.date(AuditLog.fecha_hora) >= desde)
        if hasta:
            stmt = stmt.where(func.date(AuditLog.fecha_hora) <= hasta)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        stmt = stmt.group_by(func.date(AuditLog.fecha_hora)).order_by(func.date(AuditLog.fecha_hora).asc())
        result = await self._session.execute(stmt)
        return [{"fecha": str(r[0]), "total": r[1]} for r in result.fetchall()]

    async def metricas_por_docente(
        self,
        actor_id: uuid.UUID | None = None,
    ) -> list[dict]:
        stmt = (
            select(
                AuditLog.actor_id,
                AuditLog.accion,
                func.count(AuditLog.id).label("total"),
                func.max(AuditLog.fecha_hora).label("ultima_fecha"),
            )
            .where(AuditLog.tenant_id == self._tenant_id)
        )
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        stmt = stmt.group_by(AuditLog.actor_id, AuditLog.accion).order_by(AuditLog.actor_id)
        result = await self._session.execute(stmt)
        return [
            {"actor_id": str(r[0]), "accion": r[1], "total": r[2], "ultima_fecha": r[3]}
            for r in result.fetchall()
        ]

    async def recientes(self, limit: int = 200) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == self._tenant_id)
            .order_by(AuditLog.fecha_hora.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_con_filtros(
        self,
        fecha_desde: datetime | None = None,
        fecha_hasta: datetime | None = None,
        materia_id: uuid.UUID | None = None,
        usuario_id: uuid.UUID | None = None,
        accion: str | None = None,
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == self._tenant_id)
        )
        if fecha_desde:
            stmt = stmt.where(AuditLog.fecha_hora >= fecha_desde)
        if fecha_hasta:
            stmt = stmt.where(AuditLog.fecha_hora <= fecha_hasta)
        if materia_id:
            stmt = stmt.where(AuditLog.materia_id == materia_id)
        if usuario_id:
            stmt = stmt.where(AuditLog.actor_id == usuario_id)
        if accion:
            stmt = stmt.where(AuditLog.accion == accion)
        stmt = stmt.order_by(AuditLog.fecha_hora.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
