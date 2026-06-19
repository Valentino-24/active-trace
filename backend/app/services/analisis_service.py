"""Analisis service — analytical computations and report generation.

Pure functions at the top (testable without DB), followed by the
AnalisisService class that coordinates the repository and builds
response objects.

All public service methods are read-only — no writes, no transactions.
"""

from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal
from typing import Any

from fastapi.responses import StreamingResponse

from app.repositories.analisis_repository import AnalisisRepository
from app.schemas.analisis import (
    ActividadNota,
    AtrasadoRow,
    AtrasadosResponse,
    MonitorGeneralResponse,
    MonitorGeneralRow,
    MonitorSeguimientoResponse,
    MonitorSeguimientoRow,
    NotasFinalesResponse,
    NotasFinalesRow,
    RankingResponse,
    RankingRow,
    ReporteRapidoResponse,
    SinCorregirRow,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Pure functions (trivially testable — zero dependencies)
# ═══════════════════════════════════════════════════════════════════════════════


def es_atrasado(
    total_actividades: int,
    aprobadas: int,
    faltantes: int,
) -> bool:
    """True if atrasado per RN-06: faltantes > 0 or aprobadas < total."""
    if total_actividades == 0:
        return False
    return faltantes > 0 or aprobadas < total_actividades


def compute_ranking(
    alumnos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank students by approved count (RN-09). Excludes 0-aprobadas."""
    filtered = [a for a in alumnos if a["aprobadas"] > 0]

    # Sort descending by aprobadas, then by apellido for deterministic order
    filtered.sort(key=lambda a: (-a["aprobadas"], a["apellido"], a["nombre"]))

    result: list[dict[str, Any]] = []
    current_pos = 0
    prev_count = None

    for i, alumno in enumerate(filtered):
        if alumno["aprobadas"] != prev_count:
            current_pos = i + 1
            prev_count = alumno["aprobadas"]

        total = alumno["total"]
        pct = (alumno["aprobadas"] / total * 100) if total > 0 else 0.0

        alumno_name = f"{alumno['apellido']}, {alumno['nombre']}"

        result.append({
            "posicion": current_pos,
            "entrada_padron_id": alumno["entrada_padron_id"],
            "alumno": alumno_name,
            "aprobadas": alumno["aprobadas"],
            "total": alumno["total"],
            "porcentaje_aprobacion": round(pct, 2),
        })

    return result


def compute_nota_final(
    notas: list[float | None],
    umbral_pct: float = 0.60,
) -> tuple[float | None, bool]:
    """Average of numeric notas, compare against umbral_pct * 100."""
    numeric_notas = [n for n in notas if n is not None]
    if not numeric_notas:
        return (None, False)

    promedio = sum(numeric_notas) / len(numeric_notas)
    aprobado = promedio >= (umbral_pct * 100)

    return (round(promedio, 2), aprobado)


def compute_avance_pct(aprobadas: int, total: int) -> float:
    """Percentage of approved activities over total."""
    if total == 0:
        return 0.0
    return round((aprobadas / total) * 100, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Service class (coordinates repository)
# ═══════════════════════════════════════════════════════════════════════════════


class AnalisisService:
    """Service for analytical queries and reports.

    All public methods receive db and tenant_id explicitly for
    request-scoped dependency injection.
    """

    def __init__(self, db, tenant_id: uuid.UUID):
        self._db = db
        self._tenant_id = tenant_id
        self._repo = AnalisisRepository(session=db, tenant_id=tenant_id)

    async def listar_atrasados(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> AtrasadosResponse:
        """List students who are atrasado for a materia+cohorte.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            AtrasadosResponse with students in atraso.
        """
        actividades = await self._repo.list_actividades(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        if not actividades:
            return AtrasadosResponse(items=[], total=0)

        calificaciones = await self._repo.list_alumnos_con_calificaciones(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        # Group calificaciones by student
        alumnos_map: dict[uuid.UUID, dict[str, Any]] = {}
        for row in calificaciones:
            ep_id = row["entrada_padron_id"]
            if ep_id not in alumnos_map:
                alumnos_map[ep_id] = {
                    "entrada_padron_id": ep_id,
                    "alumno": f"{row['apellidos']}, {row['nombre']}",
                    "actividades_faltantes": set(),
                    "actividades_desaprobadas": set(),
                    "aprobadas": 0,
                    "total_con_datos": 0,
                }

            if row["actividad_nombre"] is not None:
                alumnos_map[ep_id]["total_con_datos"] += 1
                if row["aprobado"]:
                    alumnos_map[ep_id]["aprobadas"] += 1
                else:
                    alumnos_map[ep_id]["actividades_desaprobadas"].add(
                        row["actividad_nombre"]
                    )

        # Determine which activities are missing per student
        all_activities = set(actividades)
        items: list[AtrasadoRow] = []

        for ep_id, info in alumnos_map.items():
            missing = all_activities - set(
                f"{r.get('actividad_nombre', '')}" for r in calificaciones
                if r["entrada_padron_id"] == ep_id and r["actividad_nombre"] is not None
            )

            # But we need to track what activities each student actually has
            student_califs = [
                r for r in calificaciones
                if r["entrada_padron_id"] == ep_id and r["actividad_nombre"] is not None
            ]
            student_activities = {r["actividad_nombre"] for r in student_califs}
            missing_activities = all_activities - student_activities

            faltantes = len(missing_activities)
            desaprobadas = len(info["actividades_desaprobadas"])
            aprobadas = info["aprobadas"]
            total_alumno = len(student_activities)
            total_atrasos = faltantes + desaprobadas

            if total_alumno == 0:
                # Student has no calificaciones data → skip (sin datos)
                continue

            # Check if atrasado
            if not es_atrasado(
                total_actividades=len(all_activities),
                aprobadas=aprobadas,
                faltantes=faltantes,
            ):
                continue  # Alumno al día → skip

            avance = compute_avance_pct(
                aprobadas=aprobadas,
                total=len(all_activities),
            )

            items.append(AtrasadoRow(
                entrada_padron_id=ep_id,
                alumno=info["alumno"],
                actividades_faltantes=sorted(missing_activities),
                actividades_desaprobadas=sorted(info["actividades_desaprobadas"]),
                total_atrasos=total_atrasos,
                avance_pct=avance,
            ))

        return AtrasadosResponse(items=items, total=len(items))

    async def get_ranking(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> RankingResponse:
        """Get ranking of students by approved activities.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            RankingResponse with sorted ranking.
        """
        actividades = await self._repo.list_actividades(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )
        total_actividades = len(actividades)

        alumnos_counts = await self._repo.count_aprobadas_por_alumno(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        alumnos_list = [
            {
                "entrada_padron_id": ep_id,
                "apellido": apellido,
                "nombre": nombre,
                "aprobadas": aprobadas,
                "total": max(total, total_actividades),
            }
            for ep_id, apellido, nombre, aprobadas, total in alumnos_counts
        ]

        ranking = compute_ranking(alumnos_list)

        items = [
            RankingRow(
                posicion=r["posicion"],
                entrada_padron_id=r["entrada_padron_id"],
                alumno=r["alumno"],
                actividades_aprobadas=r["aprobadas"],
                total_actividades=total_actividades,
                porcentaje_aprobacion=r["porcentaje_aprobacion"],
            )
            for r in ranking
        ]

        return RankingResponse(
            items=items,
            total_actividades=total_actividades,
            total_alumnos=len(items),
        )

    async def get_reportes_rapidos(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> ReporteRapidoResponse:
        """Get consolidated metrics for a materia+cohorte.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            ReporteRapidoResponse with aggregated metrics.
        """
        actividades = await self._repo.list_actividades(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        if not actividades:
            return ReporteRapidoResponse(
                total_alumnos=0,
                alumnos_atrasados=0,
                actividades_sin_corregir=0,
                porcentaje_aprobacion_general=0.0,
                estado="sin_datos",
            )

        total_alumnos = await self._repo.count_entradas_padron(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        atrasados_resp = await self.listar_atrasados(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )
        alumnos_atrasados = atrasados_resp.total

        sin_corregir = await self._repo.list_sin_corregir(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        # Count alunos with all activities approved
        calificaciones = await self._repo.list_alumnos_con_calificaciones(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        # Group by student
        alumnos_data: dict[uuid.UUID, dict] = {}
        for row in calificaciones:
            ep_id = row["entrada_padron_id"]
            if ep_id not in alumnos_data:
                alumnos_data[ep_id] = {
                    "total": 0,
                    "aprobadas": 0,
                }
            if row["actividad_nombre"] is not None:
                alumnos_data[ep_id]["total"] += 1
                if row["aprobado"]:
                    alumnos_data[ep_id]["aprobadas"] += 1

        alumnos_con_todo = sum(
            1 for d in alumnos_data.values()
            if d["total"] > 0 and d["aprobadas"] == d["total"]
            and d["total"] == len(actividades)
        )

        total_con_datos = sum(1 for d in alumnos_data.values() if d["total"] > 0)
        pct_gral = (
            (alumnos_con_todo / total_con_datos * 100)
            if total_con_datos > 0
            else 0.0
        )

        return ReporteRapidoResponse(
            total_alumnos=total_alumnos,
            alumnos_atrasados=alumnos_atrasados,
            actividades_sin_corregir=len(sin_corregir),
            porcentaje_aprobacion_general=round(pct_gral, 2),
            estado="con_datos",
        )

    async def get_notas_finales(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> NotasFinalesResponse:
        """Get final grades summary per student.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            NotasFinalesResponse with per-student averages.
        """
        umbral_pct, valores_aprobatorios = await self._repo.get_umbral_efectivo(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
        )

        calificaciones = await self._repo.list_alumnos_con_calificaciones(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        # Group by student
        alumnos_map: dict[uuid.UUID, dict[str, Any]] = {}
        for row in calificaciones:
            ep_id = row["entrada_padron_id"]
            if ep_id not in alumnos_map:
                alumnos_map[ep_id] = {
                    "entrada_padron_id": ep_id,
                    "alumno": f"{row['apellidos']}, {row['nombre']}",
                    "notas": [],
                    "actividades": [],
                }

            if row["actividad_nombre"] is not None:
                nota = row["nota"]
                nota_textual = row["nota_textual"]
                aprobado = row["aprobado"] or False

                alumnos_map[ep_id]["notas"].append(nota)
                alumnos_map[ep_id]["actividades"].append(
                    ActividadNota(
                        nombre=row["actividad_nombre"],
                        nota=Decimal(str(nota)) if nota is not None else None,
                        nota_textual=nota_textual,
                        aprobado=aprobado,
                    )
                )

        items: list[NotasFinalesRow] = []
        for info in alumnos_map.values():
            if not info["actividades"]:
                continue  # skip students with no data

            promedio, aprobado = compute_nota_final(
                info["notas"],
                umbral_pct=umbral_pct,
            )

            items.append(NotasFinalesRow(
                entrada_padron_id=info["entrada_padron_id"],
                alumno=info["alumno"],
                promedio=promedio,
                aprobado=aprobado,
                umbral_aplicado=umbral_pct,
                actividades=info["actividades"],
            ))

        return NotasFinalesResponse(items=items)

    async def exportar_sin_corregir(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        asignacion_ids: list[uuid.UUID] | None = None,
    ) -> StreamingResponse:
        """Export textual activities without grades as CSV.

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.
            asignacion_ids: Optional scope filter.

        Returns:
            StreamingResponse with CSV content.
        """
        items = await self._repo.list_sin_corregir(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            asignacion_ids=asignacion_ids,
        )

        output = io.StringIO()
        output.write("\ufeff")  # UTF-8 BOM for Excel

        writer = csv.writer(output)
        writer.writerow(["Alumno", "Actividad", "Nota Textual"])

        for alumno, actividad, nota_textual in items:
            writer.writerow([alumno, actividad, nota_textual or ""])

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=\"sin_corregir.csv\"",
            },
        )

    async def monitor_general(
        self,
        materia_id: uuid.UUID | None = None,
        comision: str | None = None,
        regional: str | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> MonitorGeneralResponse:
        """Get general monitor view with optional filters.

        Args:
            materia_id: Optional materia filter.
            comision: Optional comision filter.
            regional: Optional regional filter.
            q: Optional text search.
            skip: Pagination offset.
            limit: Max records per page.

        Returns:
            MonitorGeneralResponse with paginated results.
        """
        rows, total = await self._repo.monitor_query(
            materia_id=materia_id,
            comision=comision,
            regional=regional,
            q=q,
            skip=skip,
            limit=limit,
        )

        items = [
            MonitorGeneralRow(
                entrada_padron_id=r["entrada_padron_id"],
                alumno=r["alumno"],
                estado=r["estado"],
                actividades_aprobadas=r["actividades_aprobadas"],
                total_actividades=r["total_actividades"],
                porcentaje_avance=r["porcentaje_avance"],
            )
            for r in rows
        ]

        return MonitorGeneralResponse(items=items, total=total)

    async def monitor_seguimiento(
        self,
        materia_id: uuid.UUID | None = None,
        alumno_id: uuid.UUID | None = None,
        asignacion_ids: list[uuid.UUID] | None = None,
        desde: str | None = None,
        hasta: str | None = None,
    ) -> MonitorSeguimientoResponse:
        """Get detailed seguimiento data.

        Args:
            materia_id: Optional materia filter.
            alumno_id: Optional student filter.
            asignacion_ids: Optional scope filter.
            desde: Optional start date filter.
            hasta: Optional end date filter.

        Returns:
            MonitorSeguimientoResponse with per-activity detail.
        """
        rows = await self._repo.monitor_seguimiento_query(
            materia_id=materia_id,
            alumno_id=alumno_id,
            asignacion_ids=asignacion_ids,
            desde=desde,
            hasta=hasta,
        )

        items = [
            MonitorSeguimientoRow(
                entrada_padron_id=r["entrada_padron_id"],
                alumno=r["alumno"],
                actividad_nombre=r["actividad_nombre"],
                nota=Decimal(str(r["nota"])) if r["nota"] is not None else None,
                nota_textual=r["nota_textual"],
                resultado=r["resultado"],
                estado_general=r["estado_general"],
            )
            for r in rows
        ]

        return MonitorSeguimientoResponse(items=items, total=len(items))
