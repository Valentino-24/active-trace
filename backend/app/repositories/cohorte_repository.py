"""Cohorte repository — tenant-scoped data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.models.cohorte import Cohorte
from app.repositories.base import BaseRepository


class CohorteRepository(BaseRepository[Cohorte]):
    """Repository for Cohorte entities with tenant scoping."""

    _model_cls = Cohorte

    async def list_by_carrera(self, carrera_id: uuid.UUID) -> Sequence[Cohorte]:
        """List all cohorts for a given carrera within the tenant.

        Args:
            carrera_id: UUID of the carrera.

        Returns:
            Sequence of Cohorte records (non-deleted).
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            Cohorte.carrera_id == carrera_id  # type: ignore[arg-type]
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
