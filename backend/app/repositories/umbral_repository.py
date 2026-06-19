"""UmbralMateria repository — tenant-scoped data access for passing thresholds.

Provides the inheritance-aware get_effective_umbral query that implements
the RN-03 chain: specific asignacion → materia default → hardcoded 0.60.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.umbral_materia import UmbralMateria
from app.repositories.base import BaseRepository

# Default values when no UmbralMateria is configured (RN-03 fallback)
_DEFAULT_UMBRAL_PCT = 0.600
_DEFAULT_VALORES_APROBATORIOS: list[str] | None = None


class UmbralMateriaRepository(BaseRepository[UmbralMateria]):
    """Repository for UmbralMateria entities with tenant scoping."""

    _model_cls = UmbralMateria

    async def get_effective_umbral(
        self,
        asignacion_id: uuid.UUID,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> tuple[float, list[str] | None]:
        """Resolve the effective umbral following the RN-03 inheritance chain.

        1. Look for an UmbralMateria with the exact (materia, cohorte, asignacion_id).
        2. If not found, look for a materia-wide default (asignacion_id IS NULL).
        3. If neither exists, return the hardcoded default (0.60, None).

        Args:
            asignacion_id: FK to the teaching assignment.
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.

        Returns:
            Tuple of (umbral_pct, valores_aprobatorios).
        """
        # Step 1: specific asignacion
        stmt_specific = (
            self._exclude_deleted(self._stmt())
            .where(UmbralMateria.materia_id == materia_id)
            .where(UmbralMateria.cohorte_id == cohorte_id)
            .where(UmbralMateria.asignacion_id == asignacion_id)
        )
        result = await self._session.execute(stmt_specific)
        umbral = result.scalar_one_or_none()
        if umbral is not None:
            return (umbral.umbral_pct, umbral.valores_aprobatorios)

        # Step 2: materia-wide default (asignacion_id IS NULL)
        stmt_default = (
            self._exclude_deleted(self._stmt())
            .where(UmbralMateria.materia_id == materia_id)
            .where(UmbralMateria.cohorte_id == cohorte_id)
            .where(UmbralMateria.asignacion_id.is_(None))
        )
        result = await self._session.execute(stmt_default)
        umbral = result.scalar_one_or_none()
        if umbral is not None:
            return (umbral.umbral_pct, umbral.valores_aprobatorios)

        # Step 3: hardcoded default
        return (_DEFAULT_UMBRAL_PCT, _DEFAULT_VALORES_APROBATORIOS)

    async def upsert(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_id: uuid.UUID | None,
        umbral_pct: float | None = None,
        valores_aprobatorios: list[str] | None = None,
    ) -> UmbralMateria:
        """Insert or update an UmbralMateria record.

        Uses PostgreSQL ON CONFLICT on the unique constraint
        (tenant_id, materia_id, cohorte_id, asignacion_id).

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_id: FK to Asignacion (None for materia-wide default).
            umbral_pct: New threshold value (keeps existing if None).
            valores_aprobatorios: New approval values (keeps existing if None).

        Returns:
            The created or updated UmbralMateria instance.
        """
        # Due to the use of generic repositories and tenant_id auto-assignment,
        # we use a direct upsert approach via session merge or insert+update.
        # Since we need the tenant_id in the ON CONFLICT target, we use
        # a raw PostgreSQL INSERT ... ON CONFLICT ... DO UPDATE approach.

        # Load existing if any
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(UmbralMateria.materia_id == materia_id)
            .where(UmbralMateria.cohorte_id == cohorte_id)
            .where(
                UmbralMateria.asignacion_id.is_(None)
                if asignacion_id is None
                else UmbralMateria.asignacion_id == asignacion_id
            )
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            # Update existing
            if umbral_pct is not None:
                existing.umbral_pct = umbral_pct
            if valores_aprobatorios is not None:
                existing.valores_aprobatorios = valores_aprobatorios
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        # Create new
        instance = await self.create(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_id=asignacion_id,
            umbral_pct=umbral_pct if umbral_pct is not None else _DEFAULT_UMBRAL_PCT,
            valores_aprobatorios=valores_aprobatorios,
        )
        return instance

    async def list_by_filters(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> list[UmbralMateria]:
        """List all umbrales for a given (materia, cohorte).

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.

        Returns:
            List of UmbralMateria records (both specific and materia-wide).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(UmbralMateria.materia_id == materia_id)
            .where(UmbralMateria.cohorte_id == cohorte_id)
            .order_by(UmbralMateria.asignacion_id.asc().nullsfirst())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
