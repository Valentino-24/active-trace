"""Tarea repositories — tenant-scoped data access for tasks and comments.

Two repositories:
    - TareaRepository: CRUD + filtered queries (list_por_asignado, list_con_filtros).
    - ComentarioTareaRepository: immutable audit records for task comments.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.comentario_tarea import ComentarioTarea
from app.models.tarea import Tarea
from app.repositories.base import BaseRepository


class TareaRepository(BaseRepository[Tarea]):
    """Repository for internal tasks (tareas)."""

    _model_cls = Tarea

    async def list_por_asignado(
        self,
        asignado_a: uuid.UUID,
        *,
        estado: str | None = None,
        materia_id: uuid.UUID | None = None,
    ) -> Sequence[Tarea]:
        """List non-deleted tasks assigned to a specific user.

        Optional filters: estado, materia_id.
        Ordered by created_at DESC (most recent first).
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            Tarea.asignado_a == asignado_a
        )
        if estado is not None:
            stmt = stmt.where(Tarea.estado == estado)
        if materia_id is not None:
            stmt = stmt.where(Tarea.materia_id == materia_id)

        stmt = stmt.order_by(Tarea.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_con_filtros(
        self,
        *,
        tenant_id: uuid.UUID,
        asignado_a: uuid.UUID | None = None,
        asignado_por: uuid.UUID | None = None,
        materia_id: uuid.UUID | None = None,
        estado: str | None = None,
        q: str | None = None,
    ) -> Sequence[Tarea]:
        """Admin list with combined filters and free-text ILIKE search.

        All filters are combined with AND logic.
        Ordered by created_at DESC (most recent first).
        """
        stmt = self._exclude_deleted(self._stmt())

        if asignado_a is not None:
            stmt = stmt.where(Tarea.asignado_a == asignado_a)
        if asignado_por is not None:
            stmt = stmt.where(Tarea.asignado_por == asignado_por)
        if materia_id is not None:
            stmt = stmt.where(Tarea.materia_id == materia_id)
        if estado is not None:
            stmt = stmt.where(Tarea.estado == estado)
        if q is not None and q.strip():
            stmt = stmt.where(Tarea.descripcion.ilike(f"%{q.strip()}%"))

        stmt = stmt.order_by(Tarea.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()


class ComentarioTareaRepository(BaseRepository[ComentarioTarea]):
    """Repository for task comments (immutable — append-only).

    ComentarioTarea does NOT have SoftDeleteMixin — records
    are permanent audit trail entries.
    """

    _model_cls = ComentarioTarea

    async def create(
        self,
        *,
        tarea_id: uuid.UUID,
        autor_id: uuid.UUID,
        texto: str,
        **kwargs: object,
    ) -> ComentarioTarea:
        """Create a new task comment (immutable audit record)."""
        instance = ComentarioTarea(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            tarea_id=tarea_id,
            autor_id=autor_id,
            texto=texto,
            creado_at=kwargs.get("creado_at", datetime.now(UTC)),
        )
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def list_por_tarea(
        self, tarea_id: uuid.UUID,
    ) -> Sequence[ComentarioTarea]:
        """List all comments for a task, ordered ASC by creado_at."""
        stmt = (
            select(ComentarioTarea)
            .where(ComentarioTarea.tarea_id == tarea_id)
            .where(ComentarioTarea.tenant_id == self._tenant_id)
            .order_by(ComentarioTarea.creado_at.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
