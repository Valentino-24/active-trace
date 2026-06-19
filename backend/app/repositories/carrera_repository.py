"""Carrera repository — tenant-scoped data access."""

from __future__ import annotations

from sqlalchemy import select

from app.models.carrera import Carrera
from app.repositories.base import BaseRepository


class CarreraRepository(BaseRepository[Carrera]):
    """Repository for Carrera entities with tenant scoping."""

    _model_cls = Carrera

    async def get_by_codigo(self, codigo: str) -> Carrera | None:
        """Look up a carrera by codigo within the current tenant.

        Args:
            codigo: The unique code to search for.

        Returns:
            Carrera if found and not deleted, None otherwise.
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            Carrera.codigo == codigo  # type: ignore[arg-type]
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
