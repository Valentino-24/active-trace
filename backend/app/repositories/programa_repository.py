"""ProgramaRepository — tenant-scoped CRUD for syllabus documents."""

from __future__ import annotations

import uuid
from typing import Sequence

from app.models.programa_materia import ProgramaMateria
from app.repositories.base import BaseRepository


class ProgramaRepository(BaseRepository[ProgramaMateria]):
    """Repository for syllabus/program documents."""

    _model_cls = ProgramaMateria

    async def list_con_filtros(
        self,
        *,
        tenant_id: uuid.UUID,
        materia_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
    ) -> Sequence[ProgramaMateria]:
        """List programs with optional filters."""
        stmt = self._exclude_deleted(self._stmt())

        if materia_id is not None:
            stmt = stmt.where(ProgramaMateria.materia_id == materia_id)
        if cohorte_id is not None:
            stmt = stmt.where(ProgramaMateria.cohorte_id == cohorte_id)

        stmt = stmt.order_by(ProgramaMateria.created_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
