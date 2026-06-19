"""Calificacion repository — tenant-scoped data access for grade records.

Provides CRUD, bulk upsert, filtered listing, and the detectar_sin_nota
query used by the finalizacion flow (F1.2).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.models.calificacion import Calificacion
from app.repositories.base import BaseRepository


class CalificacionRepository(BaseRepository[Calificacion]):
    """Repository for Calificacion entities with tenant scoping."""

    _model_cls = Calificacion

    async def bulk_create(
        self,
        calificaciones: list[Calificacion],
    ) -> list[Calificacion]:
        """Insert multiple Calificacion records with flush.

        Args:
            calificaciones: List of Calificacion instances (must already
                have tenant_id and all required FK values set).

        Returns:
            The same list with IDs populated after flush.
        """
        for c in calificaciones:
            self._session.add(c)
        await self._session.flush()
        return calificaciones

    async def list_by_filters(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Calificacion], int]:
        """List calificaciones with optional filters and pagination.

        Args:
            materia_id: Required filter by materia.
            cohorte_id: Required filter by cohorte.
            asignacion_id: Optional filter by asignacion (PROFESOR scope).
            skip: Pagination offset.
            limit: Max records to return.

        Returns:
            Tuple of (calificaciones list, total count).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Calificacion.materia_id == materia_id)
            .where(Calificacion.cohorte_id == cohorte_id)
            .options(joinedload(Calificacion.entrada_padron))
            .order_by(Calificacion.created_at.desc())
        )

        if asignacion_id is not None:
            stmt = stmt.where(Calificacion.asignacion_id == asignacion_id)

        # Count
        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        # Paginate
        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        calificaciones = list(result.scalars().all())

        return calificaciones, total

    async def list_by_asignacion(
        self,
        asignacion_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Calificacion], int]:
        """List calificaciones filtered by teaching assignment.

        Args:
            asignacion_id: FK to Asignacion.
            skip: Pagination offset.
            limit: Max records to return.

        Returns:
            Tuple of (calificaciones list, total count).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Calificacion.asignacion_id == asignacion_id)
            .options(joinedload(Calificacion.entrada_padron))
            .order_by(Calificacion.created_at.desc())
        )

        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        calificaciones = list(result.scalars().all())

        return calificaciones, total

    async def count_by_filters(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> int:
        """Count calificaciones for a given (materia, cohorte).

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.

        Returns:
            Total count of non-deleted records.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Calificacion.materia_id == materia_id)
            .where(Calificacion.cohorte_id == cohorte_id)
        )
        result = await self._session.execute(stmt)
        return len(result.scalars().all())

    async def find_by_entrada_padron_y_actividad(
        self,
        entrada_padron_id: uuid.UUID,
        actividad_nombre: str,
    ) -> Calificacion | None:
        """Find a specific grade by student entry and activity name.

        Args:
            entrada_padron_id: FK to EntradaPadron.
            actividad_nombre: Activity/assignment name.

        Returns:
            Calificacion if found, None otherwise.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Calificacion.entrada_padron_id == entrada_padron_id)
            .where(Calificacion.actividad_nombre == actividad_nombre)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def detectar_sin_nota(
        self,
        cohorte_id: uuid.UUID,
        materia_id: uuid.UUID,
        actividad_nombre: str,
    ) -> list[Calificacion]:
        """Find textual-grade activities that were delivered but have no grade.

        This is used by the finalizacion flow (F1.2) to identify TPs
        that students submitted but the teacher hasn't graded yet.

        Returns Calificacion records where:
        - The actividad matches
        - nota_textual is NULL (not graded yet)
        - nota is NULL (not graded yet)
        - The activity is textual-type (we check via metadata)

        Args:
            cohorte_id: FK to Cohorte.
            materia_id: FK to Materia.
            actividad_nombre: Activity name to check.

        Returns:
            List of Calificacion records without grades.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Calificacion.materia_id == materia_id)
            .where(Calificacion.cohorte_id == cohorte_id)
            .where(Calificacion.actividad_nombre == actividad_nombre)
            .where(Calificacion.nota.is_(None))
            .where(Calificacion.nota_textual.is_(None))
            .options(joinedload(Calificacion.entrada_padron))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
