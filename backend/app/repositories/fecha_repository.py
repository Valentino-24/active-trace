"""FechaRepository — tenant-scoped CRUD for evaluation dates."""

from __future__ import annotations

import uuid
from typing import Sequence

from app.models.fecha_academica import FechaAcademica
from app.repositories.base import BaseRepository


class FechaRepository(BaseRepository[FechaAcademica]):
    """Repository for academic evaluation dates."""

    _model_cls = FechaAcademica

    async def list_con_filtros(
        self,
        *,
        tenant_id: uuid.UUID,
        materia_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
        tipo: str | None = None,
        periodo: str | None = None,
    ) -> Sequence[FechaAcademica]:
        """List dates with combined filters (AND logic)."""
        stmt = self._exclude_deleted(self._stmt())

        if materia_id is not None:
            stmt = stmt.where(FechaAcademica.materia_id == materia_id)
        if cohorte_id is not None:
            stmt = stmt.where(FechaAcademica.cohorte_id == cohorte_id)
        if tipo is not None:
            stmt = stmt.where(FechaAcademica.tipo == tipo)
        if periodo is not None:
            stmt = stmt.where(FechaAcademica.periodo == periodo)

        stmt = stmt.order_by(FechaAcademica.fecha.asc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
