"""Materia repository — tenant-scoped data access."""

from __future__ import annotations

from sqlalchemy import select

from app.models.materia import Materia
from app.repositories.base import BaseRepository


class MateriaRepository(BaseRepository[Materia]):
    """Repository for Materia entities with tenant scoping."""

    _model_cls = Materia

    async def get_by_codigo(self, codigo: str) -> Materia | None:
        """Look up a materia by codigo within the current tenant.

        Args:
            codigo: The unique code to search for.

        Returns:
            Materia if found and not deleted, None otherwise.
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            Materia.codigo == codigo  # type: ignore[arg-type]
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
