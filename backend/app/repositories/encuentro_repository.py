"""Encuentro repositories — tenant-scoped data access for slots and instances.

Provides:
    - SlotEncuentroRepository: CRUD + list by materia
    - InstanciaEncuentroRepository: CRUD + list by materia/fechas + update estado + count
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Sequence

from sqlalchemy import select, func, update

from app.models.instancia_encuentro import EstadoInstancia, InstanciaEncuentro
from app.models.slot_encuentro import SlotEncuentro
from app.repositories.base import BaseRepository


class SlotEncuentroRepository(BaseRepository[SlotEncuentro]):
    """Repository for SlotEncuentro entities with tenant scoping."""

    _model_cls = SlotEncuentro

    async def list_por_materia(
        self, materia_id: uuid.UUID,
    ) -> Sequence[SlotEncuentro]:
        """List all non-deleted slots for a materia."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(SlotEncuentro.materia_id == materia_id)
            .order_by(SlotEncuentro.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class InstanciaEncuentroRepository(BaseRepository[InstanciaEncuentro]):
    """Repository for InstanciaEncuentro entities with tenant scoping."""

    _model_cls = InstanciaEncuentro

    async def list_por_materia_fechas(
        self,
        materia_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> Sequence[InstanciaEncuentro]:
        """List instances filtered by materia and/or date range."""
        stmt = self._exclude_deleted(self._stmt())
        if materia_id is not None:
            stmt = stmt.where(InstanciaEncuentro.materia_id == materia_id)
        if desde is not None:
            stmt = stmt.where(InstanciaEncuentro.fecha >= desde)
        if hasta is not None:
            stmt = stmt.where(InstanciaEncuentro.fecha <= hasta)
        stmt = stmt.order_by(InstanciaEncuentro.fecha.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_por_slot(
        self, slot_id: uuid.UUID,
    ) -> Sequence[InstanciaEncuentro]:
        """List all instances belonging to a slot."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(InstanciaEncuentro.slot_id == slot_id)
            .order_by(InstanciaEncuentro.fecha.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_estado(
        self,
        id: uuid.UUID,
        estado: str,
        **extra: object,
    ) -> InstanciaEncuentro | None:
        """Update the estado and optional extra fields of an instance."""
        instance = await self.get(id)
        if instance is None:
            return None
        instance.estado = estado
        for field, value in extra.items():
            if value is not None:
                setattr(instance, field, value)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def count_por_materia(
        self, materia_id: uuid.UUID,
    ) -> int:
        """Count instances for a materia."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(InstanciaEncuentro.materia_id == materia_id)
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())
