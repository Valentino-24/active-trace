"""Coloquio service — creates evaluations, imports students, manages
reservations with cupo control, and registers grades.

Flow:
1. COORDINADOR creates convocatoria → imports alumnos
2. ALUMNO sees available → reserves slot (with cupo check)
3. COORDINADOR registers grades → queries metrics/agenda/registry
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluacion import Evaluacion
from app.models.reserva_evaluacion import EstadoReserva, ReservaEvaluacion
from app.models.resultado_evaluacion import ResultadoEvaluacion
from app.models.materia import Materia
from app.models.user import User
from app.repositories.coloquio_repository import (
    EvaluacionRepository,
    ReservaEvaluacionRepository,
    ResultadoEvaluacionRepository,
)


class ColoquioService:
    """Service for coloquios domain operations.

    Attributes:
        db: Database session.
        tenant_id: Current tenant for scoping.
        current_user_id: ID of the authenticated user.
    """

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._current_user_id = current_user_id
        self._ev_repo = EvaluacionRepository(session=db, tenant_id=tenant_id)
        self._reserva_repo = ReservaEvaluacionRepository(
            session=db, tenant_id=tenant_id,
        )
        self._resultado_repo = ResultadoEvaluacionRepository(
            session=db, tenant_id=tenant_id,
        )

    # ── Gestión: Convocatorias ─────────────────────────────────────────

    async def crear_convocatoria(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        tipo: str,
        instancia: str,
        dias_disponibles: int = 30,
    ) -> Evaluacion:
        """Create a new evaluacion (convocatoria).

        Returns the created Evaluacion instance.
        """
        ev = await self._ev_repo.create(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            tipo=tipo,
            instancia=instancia,
            dias_disponibles=dias_disponibles,
            activa=True,
        )
        return ev

    async def cerrar_convocatoria(self, evaluacion_id: uuid.UUID) -> Evaluacion:
        """Close a convocation by setting activa=False.

        Raises 404 if not found.
        """
        ev = await self._ev_repo.update(evaluacion_id, activa=False)
        if ev is None:
            raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
        return ev

    async def listar_convocatorias(self) -> list[dict[str, Any]]:
        """List all evaluations with derived metrics (convocados,
        reservas_activas, cupo_disponible)."""
        return await self._ev_repo.list_con_metricas()

    # ── Gestión: Importar alumnos ──────────────────────────────────────

    async def importar_alumnos(
        self,
        evaluacion_id: uuid.UUID,
        alumno_ids: list[uuid.UUID],
    ) -> dict[str, int]:
        """Import students into an evaluation by creating ResultadoEvaluacion
        records with nota_final=NULL.

        Skips duplicates (already existing resultados for this evaluacion).
        Returns dict with importados and ya_existentes counts.
        """
        # Verify evaluacion exists
        ev = await self._ev_repo.get(evaluacion_id)
        if ev is None:
            raise HTTPException(status_code=404, detail="Convocatoria no encontrada")

        existentes = await self._resultado_repo.list_por_evaluacion(evaluacion_id)
        existentes_ids = {r.alumno_id for r in existentes}

        nuevos = [
            ResultadoEvaluacion(
                tenant_id=self._tenant_id,
                evaluacion_id=evaluacion_id,
                alumno_id=aid,
                nota_final=None,
            )
            for aid in alumno_ids
            if aid not in existentes_ids
        ]

        if nuevos:
            self._db.add_all(nuevos)
            await self._db.flush()

        return {
            "importados": len(nuevos),
            "ya_existentes": len(alumno_ids) - len(nuevos),
        }

    # ── Gestión: Notas ─────────────────────────────────────────────────

    async def registrar_nota(
        self,
        resultado_id: uuid.UUID,
        nota_final: str,
    ) -> ResultadoEvaluacion:
        """Register a grade for a student's evaluation result.

        Raises 404 if not found.
        """
        result = await self._resultado_repo.update(
            resultado_id,
            nota_final=nota_final,
            registrada_at=datetime.now(),
        )
        if result is None:
            raise HTTPException(
                status_code=404, detail="Resultado no encontrado",
            )
        return result

    # ── ALUMNO: Reservas ───────────────────────────────────────────────

    async def reservar_turno(
        self,
        evaluacion_id: uuid.UUID,
        fecha_hora: datetime,
    ) -> ReservaEvaluacion:
        """Reserve a slot for an evaluation.

        Checks cupo: count of active reservas < dias_disponibles.
        Raises 409 if full, 404 if evaluacion not found or inactive.
        """
        ev = await self._ev_repo.get(evaluacion_id)
        if ev is None or not ev.activa:
            raise HTTPException(
                status_code=404, detail="Convocatoria no encontrada o inactiva",
            )

        cupo_usado = await self._reserva_repo.count_activas_por_evaluacion(
            evaluacion_id,
        )
        if cupo_usado >= ev.dias_disponibles:
            raise HTTPException(
                status_code=409,
                detail="No hay cupo disponible para esta convocatoria",
            )

        reserva = await self._reserva_repo.create(
            evaluacion_id=evaluacion_id,
            alumno_id=self._current_user_id,
            fecha_hora=fecha_hora,
            estado=EstadoReserva.Activa.value,
        )
        return reserva

    async def cancelar_reserva(self, reserva_id: uuid.UUID) -> bool:
        """Cancel a reservation by setting estado=Cancelada.

        Only the owning student can cancel their own reservation.
        Raises 404 if not found.
        """
        reserva = await self._reserva_repo.get(reserva_id)
        if reserva is None:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")

        if reserva.alumno_id != self._current_user_id:
            raise HTTPException(
                status_code=403,
                detail="No puedes cancelar una reserva de otro alumno",
            )

        updated = await self._reserva_repo.update(
            reserva_id,
            estado=EstadoReserva.Cancelada.value,
        )
        return updated is not None

    # ── ALUMNO: Consultas ──────────────────────────────────────────────

    async def listar_disponibles_para_alumno(self) -> list[dict[str, Any]]:
        """List active evaluations where the current student is habilitated
        (has a ResultadoEvaluacion record)."""
        resultados = await self._resultado_repo.list_por_alumno(
            self._current_user_id,
        )

        ev_ids_habilitated = {r.evaluacion_id for r in resultados}

        # Get active evaluations
        evaluaciones = await self._ev_repo.list_activas()

        # Get existing reservas for this alumno
        reservas = await self._reserva_repo.list_por_alumno(self._current_user_id)
        reservadas = {
            r.evaluacion_id
            for r in reservas
            if r.estado == EstadoReserva.Activa.value
        }

        disponibles = []
        for ev in evaluaciones:
            if ev.id not in ev_ids_habilitated:
                continue
            disponibles.append({
                "id": ev.id,
                "materia_id": ev.materia_id,
                "instancia": ev.instancia,
                "tipo": ev.tipo,
                "dias_disponibles": ev.dias_disponibles,
                "tiene_reserva": ev.id in reservadas,
            })
        return disponibles

    async def listar_mis_reservas(self) -> list[dict[str, Any]]:
        """List all reservations for the current student."""
        reservas = await self._reserva_repo.list_por_alumno(self._current_user_id)

        items = []
        for r in reservas:
            # Load materia info via evaluacion
            ev = await self._ev_repo.get(r.evaluacion_id)
            materia_nombre = ""
            instancia = ""
            if ev:
                materia_stmt = select(Materia).where(Materia.id == ev.materia_id)
                materia_result = await self._db.execute(materia_stmt)
                materia = materia_result.scalar_one_or_none()
                materia_nombre = materia.nombre if materia else ""
                instancia = ev.instancia

            items.append({
                "id": r.id,
                "evaluacion_id": r.evaluacion_id,
                "materia": materia_nombre,
                "instancia": instancia,
                "fecha_hora": r.fecha_hora,
                "estado": r.estado,
                "created_at": r.created_at,
            })
        return items

    # ── Consulta: Métricas ─────────────────────────────────────────────

    async def get_metricas(self) -> dict[str, int]:
        """Get aggregate metrics for the tenant."""
        # Total alumnos cargados (distinct alumno_ids in resultado)
        stmt_alumnos = select(ResultadoEvaluacion.alumno_id).where(
            ResultadoEvaluacion.tenant_id == self._tenant_id,
            ResultadoEvaluacion.deleted_at.is_(None),
        ).distinct()
        result = await self._db.execute(stmt_alumnos)
        total_alumnos = len(result.fetchall())

        # Instancias activas
        activas = await self._ev_repo.list_activas()
        total_activas = len(activas)

        # Reservas activas
        reservas_activas = await self._reserva_repo.list_activas()
        total_reservas = len(reservas_activas)

        # Notas registradas
        total_notas = await self._resultado_repo.count_notas_registradas()

        return {
            "total_alumnos_cargados": total_alumnos,
            "instancias_activas": total_activas,
            "reservas_activas": total_reservas,
            "notas_registradas": total_notas,
        }

    # ── Consulta: Agenda ───────────────────────────────────────────────

    async def get_agenda(self) -> list[dict[str, Any]]:
        """Get consolidated agenda of all active reservations."""
        reservas = await self._reserva_repo.list_activas()

        items = []
        for r in reservas:
            ev = await self._ev_repo.get(r.evaluacion_id)
            if ev is None:
                continue

            # Resolve materia name
            materia_stmt = select(Materia).where(Materia.id == ev.materia_id)
            materia_result = await self._db.execute(materia_stmt)
            materia = materia_result.scalar_one_or_none()

            # Resolve alumno name
            alumno_stmt = select(User).where(User.id == r.alumno_id)
            alumno_result = await self._db.execute(alumno_stmt)
            alumno = alumno_result.scalar_one_or_none()

            items.append({
                "id": r.id,
                "alumno": alumno.display_name if alumno else "",
                "materia": materia.nombre if materia else "",
                "fecha_hora": r.fecha_hora,
                "evaluacion": ev.instancia if ev else "",
                "estado": r.estado,
            })
        return items

    # ── Consulta: Registro ─────────────────────────────────────────────

    async def get_registro(self) -> list[dict[str, Any]]:
        """Get consolidated academic registry of graded results."""
        resultados = await self._resultado_repo.list_con_notas()

        items = []
        for r in resultados:
            ev = await self._ev_repo.get(r.evaluacion_id)
            if ev is None:
                continue

            materia_stmt = select(Materia).where(Materia.id == ev.materia_id)
            materia_result = await self._db.execute(materia_stmt)
            materia = materia_result.scalar_one_or_none()

            alumno_stmt = select(User).where(User.id == r.alumno_id)
            alumno_result = await self._db.execute(alumno_stmt)
            alumno = alumno_result.scalar_one_or_none()

            items.append({
                "id": r.id,
                "alumno": alumno.display_name if alumno else "",
                "materia": materia.nombre if materia else "",
                "instancia": ev.instancia if ev else "",
                "nota_final": r.nota_final,
                "registrada_at": r.registrada_at,
            })
        return items

    # ── Helpers ────────────────────────────────────────────────────────

    async def get_evaluacion(self, evaluacion_id: uuid.UUID) -> Evaluacion | None:
        """Get a single evaluacion by id."""
        return await self._ev_repo.get(evaluacion_id)
