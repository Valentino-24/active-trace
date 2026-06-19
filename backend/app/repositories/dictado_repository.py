"""Dictado repository — tenant-scoped data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.dictado import Dictado
from app.repositories.base import BaseRepository


class DictadoRepository(BaseRepository[Dictado]):
    """Repository for Dictado entities with tenant scoping."""

    _model_cls = Dictado

    async def list_by_materia(self, materia_id: uuid.UUID) -> Sequence[Dictado]:
        """List all dictados for a given materia within the tenant.

        Args:
            materia_id: UUID of the materia.

        Returns:
            Sequence of Dictado records (non-deleted).
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            Dictado.materia_id == materia_id  # type: ignore[arg-type]
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_by_cohorte(self, cohorte_id: uuid.UUID) -> Sequence[Dictado]:
        """List all dictados for a given cohorte within the tenant.

        Args:
            cohorte_id: UUID of the cohorte.

        Returns:
            Sequence of Dictado records (non-deleted).
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            Dictado.cohorte_id == cohorte_id  # type: ignore[arg-type]
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
