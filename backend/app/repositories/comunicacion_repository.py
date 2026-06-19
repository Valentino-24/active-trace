"""Comunicacion repository — tenant-scoped data access for communications.

Provides CRUD, batch queries by lote and estado, and state transition
operations used by the service layer and worker.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select, func, update
from sqlalchemy.orm import joinedload

from app.models.comunicacion import Comunicacion, EstadoComunicacion
from app.repositories.base import BaseRepository


class ComunicacionRepository(BaseRepository[Comunicacion]):
    """Repository for Comunicacion entities with tenant scoping."""

    _model_cls = Comunicacion

    async def list_pendientes(self, limit: int = 50) -> Sequence[Comunicacion]:
        """Fetch pending messages ordered by creation date.

        Args:
            limit: Maximum number of messages to return.

        Returns:
            Sequence of Comunicacion in Pendiente state,
            ordered by created_at (oldest first).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Comunicacion.estado == EstadoComunicacion.Pendiente.value)
            .order_by(Comunicacion.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_por_lote(
        self, lote_id: uuid.UUID,
    ) -> Sequence[Comunicacion]:
        """Fetch all messages in a batch.

        Args:
            lote_id: The batch UUID.

        Returns:
            All Comunicacion records sharing the given lote_id.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Comunicacion.lote_id == lote_id)
            .order_by(Comunicacion.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_estado(
        self, id: uuid.UUID, estado: str,
    ) -> Comunicacion | None:
        """Transition a single message to a new state.

        Args:
            id: Comunicacion ID.
            estado: Target state value.

        Returns:
            Updated Comunicacion if found, None otherwise.
        """
        instance = await self.get(id)
        if instance is None:
            return None
        instance.estado = estado
        if estado == EstadoComunicacion.Enviado.value:
            instance.enviado_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def count_por_estado(
        self, materia_id: uuid.UUID,
    ) -> dict[str, int]:
        """Aggregate counts by estado for a given materia.

        Args:
            materia_id: FK to Materia.

        Returns:
            Dict mapping estado → count.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Comunicacion.materia_id == materia_id)
            .with_only_columns(
                Comunicacion.estado,
                func.count(Comunicacion.id),
            )
            .group_by(Comunicacion.estado)
        )
        result = await self._session.execute(stmt)
        counts: dict[str, int] = {}
        for row in result.fetchall():
            counts[row[0]] = row[1]
        return counts

    async def list_pendientes_aprobacion(
        self, limit: int = 50,
    ) -> Sequence[Comunicacion]:
        """Fetch pending messages that need approval.

        Returns messages in Pendiente state that haven't been
        approved yet, ordered by creation date.

        Args:
            limit: Maximum number of messages to return.

        Returns:
            Sequence of Comunicacion needing approval.
        """
        return await self.list_pendientes(limit=limit)

    async def bulk_update_estado(
        self, lote_id: uuid.UUID, estado: str,
    ) -> int:
        """Transition all messages in a batch to a new state.

        Args:
            lote_id: The batch UUID.
            estado: Target state value.

        Returns:
            Number of records updated.
        """
        stmt = (
            update(Comunicacion)
            .where(Comunicacion.tenant_id == self._tenant_id)
            .where(Comunicacion.lote_id == lote_id)
            .where(Comunicacion.deleted_at.is_(None))
            .values(estado=estado)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def count_by_materia(
        self, materia_id: uuid.UUID,
    ) -> int:
        """Count total communications for a materia.

        Args:
            materia_id: FK to Materia.

        Returns:
            Total count of non-deleted records.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Comunicacion.materia_id == materia_id)
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())
