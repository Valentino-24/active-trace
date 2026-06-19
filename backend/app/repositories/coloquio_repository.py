"""Coloquio repositories — tenant-scoped data access for evaluaciones,
reservas, and resultados.

Three repositories following the patterns from BaseRepository[T] with
custom queries for aggregates, counts, and filtered listings.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models.evaluacion import Evaluacion
from app.models.reserva_evaluacion import EstadoReserva, ReservaEvaluacion
from app.models.resultado_evaluacion import ResultadoEvaluacion
from app.repositories.base import BaseRepository


class EvaluacionRepository(BaseRepository[Evaluacion]):
    """Repository for Evaluacion (convocatoria) entities."""

    _model_cls = Evaluacion

    async def list_activas(self) -> Sequence[Evaluacion]:
        """List all active (non-deleted, activa=True) evaluations."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Evaluacion.activa.is_(True))
            .order_by(Evaluacion.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_con_metricas(self) -> list[dict[str, Any]]:
        """List evaluations with derived metrics per evaluation.

        Returns a list of dicts with id plus:
            convocados, reservas_activas, cupo_disponible
        """
        # Subquery: count of resultados por evaluacion
        resultados_sub = (
            select(
                ResultadoEvaluacion.evaluacion_id,
                func.count(ResultadoEvaluacion.id).label("convocados"),
            )
            .where(ResultadoEvaluacion.deleted_at.is_(None))
            .group_by(ResultadoEvaluacion.evaluacion_id)
            .subquery()
        )

        # Subquery: count of active reservas por evaluacion
        reservas_sub = (
            select(
                ReservaEvaluacion.evaluacion_id,
                func.count(ReservaEvaluacion.id).label("reservas_activas"),
            )
            .where(ReservaEvaluacion.deleted_at.is_(None))
            .where(ReservaEvaluacion.estado == EstadoReserva.Activa.value)
            .group_by(ReservaEvaluacion.evaluacion_id)
            .subquery()
        )

        stmt = (
            self._exclude_deleted(self._stmt())
            .outerjoin(
                resultados_sub,
                Evaluacion.id == resultados_sub.c.evaluacion_id,
            )
            .outerjoin(
                reservas_sub,
                Evaluacion.id == reservas_sub.c.evaluacion_id,
            )
            .add_columns(
                func.coalesce(resultados_sub.c.convocados, 0).label("convocados"),
                func.coalesce(reservas_sub.c.reservas_activas, 0).label("reservas_activas"),
            )
            .order_by(Evaluacion.created_at.desc())
        )

        result = await self._session.execute(stmt)
        rows = []
        for row in result.fetchall():
            ev: Evaluacion = row[0]
            convocados = row[1]
            reservas_activas = row[2]
            rows.append({
                "id": ev.id,
                "materia_id": ev.materia_id,
                "tipo": ev.tipo,
                "instancia": ev.instancia,
                "dias_disponibles": ev.dias_disponibles,
                "activa": ev.activa,
                "created_at": ev.created_at,
                "convocados": convocados,
                "reservas_activas": reservas_activas,
                "cupo_disponible": ev.dias_disponibles - reservas_activas,
            })
        return rows


class ReservaEvaluacionRepository(BaseRepository[ReservaEvaluacion]):
    """Repository for ReservaEvaluacion (student booking) entities."""

    _model_cls = ReservaEvaluacion

    async def count_activas_por_evaluacion(self, evaluacion_id: uuid.UUID) -> int:
        """Count active (non-cancelled) reservations for an evaluation."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ReservaEvaluacion.evaluacion_id == evaluacion_id)
            .where(ReservaEvaluacion.estado == EstadoReserva.Activa.value)
            .with_only_columns(func.count(ReservaEvaluacion.id))
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def list_por_alumno(self, alumno_id: uuid.UUID) -> Sequence[ReservaEvaluacion]:
        """List all reservations for a given student."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ReservaEvaluacion.alumno_id == alumno_id)
            .order_by(ReservaEvaluacion.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_activas(self) -> Sequence[ReservaEvaluacion]:
        """List all active reservations (non-deleted, estado=Activa)."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ReservaEvaluacion.estado == EstadoReserva.Activa.value)
            .order_by(ReservaEvaluacion.fecha_hora.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class ResultadoEvaluacionRepository(BaseRepository[ResultadoEvaluacion]):
    """Repository for ResultadoEvaluacion (grade result) entities."""

    _model_cls = ResultadoEvaluacion

    async def list_por_evaluacion(
        self, evaluacion_id: uuid.UUID,
    ) -> Sequence[ResultadoEvaluacion]:
        """List all results for a given evaluation."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ResultadoEvaluacion.evaluacion_id == evaluacion_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_por_alumno(
        self, alumno_id: uuid.UUID,
    ) -> Sequence[ResultadoEvaluacion]:
        """List all results for a given student."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ResultadoEvaluacion.alumno_id == alumno_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_notas_registradas(self) -> int:
        """Count all results with a non-null nota_final."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ResultadoEvaluacion.nota_final.isnot(None))
            .with_only_columns(func.count(ResultadoEvaluacion.id))
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def list_con_notas(self) -> Sequence[ResultadoEvaluacion]:
        """List all results that have a non-null nota_final."""
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(ResultadoEvaluacion.nota_final.isnot(None))
            .order_by(ResultadoEvaluacion.registrada_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
