"""Analisis repository — cross-model analytical queries.

This repository does NOT extend BaseRepository because queries cross
multiple models (Calificacion + EntradaPadron + UmbralMateria).
Uses self._session.execute() directly with manual tenant scoping.
All queries are read-only.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calificacion import Calificacion
from app.models.padron import EntradaPadron


class AnalisisRepository:
    """Repository for analytical queries across multiple models.

    All methods accept tenant_id explicitly and apply manual tenant
    scoping (no inherited _stmt() from BaseRepository).
    """

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    # ── Queries ─────────────────────────────────────────────────────────

    async def list_actividades(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> list[str]:
        """Get distinct actividad_nombre for a materia+cohorte.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter (PROFESOR/TUTOR).

        Returns:
            List of distinct activity names.
        """
        stmt = (
            select(Calificacion.actividad_nombre)
            .where(Calificacion.tenant_id == self._tenant_id)
            .where(Calificacion.materia_id == materia_id)
            .where(Calificacion.cohorte_id == cohorte_id)
            .where(Calificacion.deleted_at.is_(None))
            .distinct()
            .order_by(Calificacion.actividad_nombre)
        )

        if asignacion_ids is not None and asignacion_ids:
            stmt = stmt.where(Calificacion.asignacion_id.in_(asignacion_ids))

        result = await self._session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def list_alumnos_con_calificaciones(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> list[dict[str, Any]]:
        """Get all students with their calificaciones for a materia+cohorte.

        Performs a LEFT JOIN from EntradaPadron (via VersionPadron) to
        Calificacion to capture students with and without grades.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            List of dicts with keys: entrada_padron_id, alumno, nombre,
            apellidos, actividad_nombre, nota, nota_textual, aprobado,
            extra_data.
        """
        from app.models.padron import VersionPadron

        stmt = (
            select(
                EntradaPadron.id.label("entrada_padron_id"),
                EntradaPadron.nombre,
                EntradaPadron.apellidos,
                Calificacion.actividad_nombre,
                Calificacion.nota,
                Calificacion.nota_textual,
                Calificacion.aprobado,
                Calificacion.extra_data,
                Calificacion.asignacion_id,
            )
            .join(
                VersionPadron,
                and_(
                    VersionPadron.id == EntradaPadron.version_id,
                    VersionPadron.activa.is_(True),
                    VersionPadron.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                Calificacion,
                and_(
                    Calificacion.entrada_padron_id == EntradaPadron.id,
                    Calificacion.materia_id == materia_id,
                    Calificacion.cohorte_id == cohorte_id,
                    Calificacion.deleted_at.is_(None),
                ),
            )
            .where(EntradaPadron.tenant_id == self._tenant_id)
            .where(EntradaPadron.deleted_at.is_(None))
            .where(VersionPadron.materia_id == materia_id)
            .where(VersionPadron.cohorte_id == cohorte_id)
        )

        if asignacion_ids is not None and asignacion_ids:
            stmt = stmt.where(
                or_(
                    Calificacion.asignacion_id.in_(asignacion_ids),
                    Calificacion.asignacion_id.is_(None),
                )
            )

        stmt = stmt.order_by(EntradaPadron.apellidos, EntradaPadron.nombre)

        result = await self._session.execute(stmt)
        rows: list[dict[str, Any]] = []
        for row in result.fetchall():
            rows.append({
                "entrada_padron_id": row.entrada_padron_id,
                "nombre": row.nombre,
                "apellidos": row.apellidos,
                "actividad_nombre": row.actividad_nombre,
                "nota": row.nota,
                "nota_textual": row.nota_textual,
                "aprobado": row.aprobado,
                "extra_data": row.extra_data,
                "asignacion_id": row.asignacion_id,
            })
        return rows

    async def count_aprobados_por_actividad(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[str, int, int]]:
        """Count total students and approved students per activity.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            List of (actividad_nombre, total_alumnos, aprobados).
        """
        stmt = (
            select(
                Calificacion.actividad_nombre,
                func.count(Calificacion.id).label("total"),
                func.sum(
                    case((Calificacion.aprobado == True, 1), else_=0)
                ).label("aprobados"),
            )
            .where(Calificacion.tenant_id == self._tenant_id)
            .where(Calificacion.materia_id == materia_id)
            .where(Calificacion.cohorte_id == cohorte_id)
            .where(Calificacion.deleted_at.is_(None))
            .group_by(Calificacion.actividad_nombre)
            .order_by(Calificacion.actividad_nombre)
        )

        if asignacion_ids is not None and asignacion_ids:
            stmt = stmt.where(Calificacion.asignacion_id.in_(asignacion_ids))

        result = await self._session.execute(stmt)
        return [(row[0], int(row[1]), int(row[2])) for row in result.fetchall()]

    async def count_aprobadas_por_alumno(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[uuid.UUID, str, str, int, int]]:
        """Count approved and total activities per student.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            List of (entrada_padron_id, apellidos, nombre, aprobadas, total).
        """
        stmt = (
            select(
                Calificacion.entrada_padron_id,
                func.count(Calificacion.id).label("total"),
                func.sum(
                    case((Calificacion.aprobado == True, 1), else_=0)
                ).label("aprobadas"),
            )
            .where(Calificacion.tenant_id == self._tenant_id)
            .where(Calificacion.materia_id == materia_id)
            .where(Calificacion.cohorte_id == cohorte_id)
            .where(Calificacion.deleted_at.is_(None))
            .group_by(Calificacion.entrada_padron_id)
        )

        if asignacion_ids is not None and asignacion_ids:
            stmt = stmt.where(Calificacion.asignacion_id.in_(asignacion_ids))

        result = await self._session.execute(stmt)
        counts: list[tuple[uuid.UUID, str, str, int, int]] = []

        # Get student names
        for row in result.fetchall():
            ep_id = row[0]
            total = int(row[1])
            aprobadas = int(row[2])

            # Get student name
            name_stmt = select(
                EntradaPadron.nombre, EntradaPadron.apellidos
            ).where(EntradaPadron.id == ep_id)
            name_result = await self._session.execute(name_stmt)
            name_row = name_result.fetchone()
            if name_row:
                counts.append((ep_id, name_row.apellidos, name_row.nombre, aprobadas, total))

        return counts

    async def list_sin_corregir(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> list[tuple[str, str, str | None]]:
        """Find textual activities with delivery but no grade.

        Queries Calificacion records where nota_textual IS NOT NULL
        (already delivered/graded textually) and nota IS NULL
        (no numeric grade). Only includes textual-type records.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            List of (alumno_name, actividad_nombre, nota_textual_status).
        """
        from app.models.padron import VersionPadron

        stmt = (
            select(
                EntradaPadron.nombre,
                EntradaPadron.apellidos,
                Calificacion.actividad_nombre,
                Calificacion.nota_textual,
            )
            .join(
                VersionPadron,
                and_(
                    VersionPadron.id == EntradaPadron.version_id,
                    VersionPadron.activa.is_(True),
                    VersionPadron.deleted_at.is_(None),
                ),
            )
            .join(
                Calificacion,
                and_(
                    Calificacion.entrada_padron_id == EntradaPadron.id,
                    Calificacion.materia_id == materia_id,
                    Calificacion.cohorte_id == cohorte_id,
                    Calificacion.deleted_at.is_(None),
                    Calificacion.nota.is_(None),
                    Calificacion.nota_textual.is_not(None),
                ),
            )
            .where(EntradaPadron.tenant_id == self._tenant_id)
            .where(EntradaPadron.deleted_at.is_(None))
            .where(VersionPadron.materia_id == materia_id)
            .where(VersionPadron.cohorte_id == cohorte_id)
        )

        if asignacion_ids is not None and asignacion_ids:
            stmt = stmt.where(Calificacion.asignacion_id.in_(asignacion_ids))

        stmt = stmt.order_by(EntradaPadron.apellidos, EntradaPadron.nombre)

        result = await self._session.execute(stmt)
        items: list[tuple[str, str, str | None]] = []
        for row in result.fetchall():
            alumno = f"{row.apellidos}, {row.nombre}"
            items.append((alumno, row.actividad_nombre, row.nota_textual))
        return items

    async def monitor_query(
        self,
        materia_id: uuid.UUID | None = None,
        comision: str | None = None,
        regional: str | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated monitor general data with dynamic filters.

        Args:
            materia_id: Optional filter by materia.
            comision: Optional filter by comision.
            regional: Optional filter by regional.
            q: Optional text search (nombre or apellidos).
            skip: Pagination offset.
            limit: Max records per page.

        Returns:
            Tuple of (rows list, total count).
        """
        from app.models.padron import VersionPadron

        # Base: all non-deleted EntradaPadron for this tenant
        base = (
            select(EntradaPadron)
            .where(EntradaPadron.tenant_id == self._tenant_id)
            .where(EntradaPadron.deleted_at.is_(None))
        )

        # Join to VersionPadron to scope by materia if needed
        if materia_id is not None:
            base = base.join(
                VersionPadron,
                and_(
                    VersionPadron.id == EntradaPadron.version_id,
                    VersionPadron.activa.is_(True),
                    VersionPadron.deleted_at.is_(None),
                    VersionPadron.materia_id == materia_id,
                ),
            )

        if comision is not None:
            base = base.where(EntradaPadron.comision == comision)

        if regional is not None:
            base = base.where(EntradaPadron.regional == regional)

        if q is not None:
            pattern = f"%{q}%"
            base = base.where(
                or_(
                    EntradaPadron.nombre.ilike(pattern),
                    EntradaPadron.apellidos.ilike(pattern),
                )
            )

        # Count
        count_stmt = select(func.count()).select_from(base.subquery())
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Paginate
        base = base.offset(skip).limit(limit).order_by(EntradaPadron.apellidos, EntradaPadron.nombre)

        result = await self._session.execute(base)
        entries = list(result.scalars().all())

        rows: list[dict[str, Any]] = []
        for entry in entries:
            # Get calificacion counts for this student
            calif_stmt = (
                select(
                    func.count(Calificacion.id).label("total"),
                    func.sum(
                        case((Calificacion.aprobado == True, 1), else_=0)
                    ).label("aprobadas"),
                )
                .where(Calificacion.entrada_padron_id == entry.id)
                .where(Calificacion.deleted_at.is_(None))
            )

            if materia_id is not None:
                calif_stmt = calif_stmt.where(Calificacion.materia_id == materia_id)

            calif_result = await self._session.execute(calif_stmt)
            calif_row = calif_result.fetchone()
            total_act = calif_row[0] if calif_row else 0
            aprobadas = calif_row[1] if calif_row and calif_row[1] is not None else 0

            if total_act == 0:
                estado = "sin_datos"
                pct = None
            elif aprobadas == total_act:
                estado = "al_dia"
                pct = 100.0
            else:
                estado = "atrasado"
                pct = (aprobadas / total_act) * 100 if total_act > 0 else 0.0

            rows.append({
                "entrada_padron_id": entry.id,
                "alumno": f"{entry.apellidos}, {entry.nombre}",
                "estado": estado,
                "actividades_aprobadas": int(aprobadas) if aprobadas else 0,
                "total_actividades": int(total_act),
                "porcentaje_avance": round(pct, 2) if pct is not None else None,
            })

        return rows, total

    async def monitor_seguimiento_query(
        self,
        materia_id: uuid.UUID | None = None,
        alumno_id: uuid.UUID | None = None,
        asignacion_ids: list[uuid.UUID] | None = None,
        desde: str | None = None,
        hasta: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get detailed seguimiento data per student per activity.

        Args:
            materia_id: Optional filter by materia.
            alumno_id: Optional filter by EntradaPadron id.
            asignacion_ids: Optional scope filter.
            desde: Optional start date filter (ISO 8601).
            hasta: Optional end date filter (ISO 8601).

        Returns:
            List of dicts with per-activity detail.
        """
        from app.models.padron import VersionPadron

        stmt = (
            select(
                EntradaPadron.id.label("entrada_padron_id"),
                EntradaPadron.nombre,
                EntradaPadron.apellidos,
                Calificacion.actividad_nombre,
                Calificacion.nota,
                Calificacion.nota_textual,
                Calificacion.aprobado,
                Calificacion.periodo,
            )
            .join(
                VersionPadron,
                and_(
                    VersionPadron.id == EntradaPadron.version_id,
                    VersionPadron.activa.is_(True),
                    VersionPadron.deleted_at.is_(None),
                ),
            )
            .join(
                Calificacion,
                and_(
                    Calificacion.entrada_padron_id == EntradaPadron.id,
                    Calificacion.deleted_at.is_(None),
                ),
            )
            .where(EntradaPadron.tenant_id == self._tenant_id)
            .where(EntradaPadron.deleted_at.is_(None))
        )

        if materia_id is not None:
            stmt = stmt.where(
                Calificacion.materia_id == materia_id,
                VersionPadron.materia_id == materia_id,
            )

        if alumno_id is not None:
            stmt = stmt.where(EntradaPadron.id == alumno_id)

        if asignacion_ids is not None and asignacion_ids:
            stmt = stmt.where(Calificacion.asignacion_id.in_(asignacion_ids))

        if desde is not None:
            stmt = stmt.where(Calificacion.periodo >= desde)

        if hasta is not None:
            stmt = stmt.where(Calificacion.periodo <= hasta)

        stmt = stmt.order_by(
            EntradaPadron.apellidos, EntradaPadron.nombre,
            Calificacion.actividad_nombre,
        )

        result = await self._session.execute(stmt)

        rows: list[dict[str, Any]] = []
        for row in result.fetchall():
            # Determine estado_general per student (al_dia = all aprobado, atrasado otherwise)
            rows.append({
                "entrada_padron_id": row.entrada_padron_id,
                "alumno": f"{row.apellidos}, {row.nombre}",
                "actividad_nombre": row.actividad_nombre,
                "nota": row.nota,
                "nota_textual": row.nota_textual,
                "resultado": "aprobado" if row.aprobado else "desaprobado",
                "estado_general": "al_dia" if row.aprobado else "atrasado",
            })

        return rows

    async def count_entradas_padron(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> int:
        """Count students in the active padron for a materia+cohorte.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter (not typically used here).

        Returns:
            Total count of entries.
        """
        from app.models.padron import VersionPadron

        stmt = (
            select(func.count(EntradaPadron.id))
            .join(
                VersionPadron,
                and_(
                    VersionPadron.id == EntradaPadron.version_id,
                    VersionPadron.activa.is_(True),
                    VersionPadron.deleted_at.is_(None),
                ),
            )
            .where(EntradaPadron.tenant_id == self._tenant_id)
            .where(EntradaPadron.deleted_at.is_(None))
            .where(VersionPadron.materia_id == materia_id)
            .where(VersionPadron.cohorte_id == cohorte_id)
        )

        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_umbral_efectivo(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> tuple[float, list[str] | None]:
        """Get the effective threshold for a materia+cohorte.

        Uses the materia-wide default (asignacion_id IS NULL).
        Falls back to 0.60 if not found.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.

        Returns:
            Tuple of (umbral_pct, valores_aprobatorios).
        """
        from app.models.umbral_materia import UmbralMateria

        stmt = (
            select(UmbralMateria.umbral_pct, UmbralMateria.valores_aprobatorios)
            .where(UmbralMateria.tenant_id == self._tenant_id)
            .where(UmbralMateria.materia_id == materia_id)
            .where(UmbralMateria.cohorte_id == cohorte_id)
            .where(UmbralMateria.asignacion_id.is_(None))
            .where(UmbralMateria.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        row = result.fetchone()
        if row:
            return (float(row.umbral_pct), row.valores_aprobatorios)
        return (0.60, None)



