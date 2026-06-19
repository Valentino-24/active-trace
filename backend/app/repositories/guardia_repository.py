"""Guardia repository — tenant-scoped data access for guardia records.

Provides CRUD, filtered listing, and export query support.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from sqlalchemy import select

from app.models.guardia import Guardia
from app.repositories.base import BaseRepository


class GuardiaRepository(BaseRepository[Guardia]):
    """Repository for Guardia entities with tenant scoping."""

    _model_cls = Guardia

    async def list_con_filtros(
        self,
        materia_id: uuid.UUID | None = None,
        estado: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> Sequence[Guardia]:
        """List guardias filtered by various criteria."""
        stmt = self._exclude_deleted(self._stmt())
        if materia_id is not None:
            stmt = stmt.where(Guardia.materia_id == materia_id)
        if estado is not None:
            stmt = stmt.where(Guardia.estado == estado)
        if desde is not None:
            stmt = stmt.where(Guardia.creada_at >= desde)
        if hasta is not None:
            stmt = stmt.where(Guardia.creada_at <= hasta)
        if asignacion_ids is not None:
            stmt = stmt.where(Guardia.asignacion_id.in_(asignacion_ids))
        stmt = stmt.order_by(Guardia.creada_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_por_asignacion(
        self, asignacion_id: uuid.UUID,
    ) -> Sequence[Guardia]:
        """List all guardias for a specific asignacion."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Guardia.asignacion_id == asignacion_id)
            .order_by(Guardia.creada_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def export_query(
        self,
        materia_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        estado: str | None = None,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> Sequence[Guardia]:
        """Fetch raw guardia data for CSV export (same as list but with joins)."""
        # Same as list_con_filtros — no join needed as we use relationships
        return await self.list_con_filtros(
            materia_id=materia_id,
            estado=estado,
            desde=desde,
            hasta=hasta,
            asignacion_ids=asignacion_ids,
        )

    async def get_with_materia(
        self, id: uuid.UUID,
    ) -> Guardia | None:
        """Get a guardia eager-loaded with materia relationship."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Guardia.id == id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
