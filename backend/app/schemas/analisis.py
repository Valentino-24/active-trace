"""Pydantic schemas for Analisis endpoints.

Covers atrasados, ranking, reportes-rapidos, notas-finales,
exportar-sin-corregir, monitor-general, and monitor-seguimiento.
All schemas use extra='forbid' as per project convention.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ── Atrasados ──────────────────────────────────────────────────────────────────


class AtrasadoRow(BaseModel):
    """A single student in atraso situation."""

    model_config = ConfigDict(extra="forbid")

    entrada_padron_id: uuid.UUID
    alumno: str = Field(..., description="Apellidos, Nombre")
    actividades_faltantes: list[str] = Field(default_factory=list)
    actividades_desaprobadas: list[str] = Field(default_factory=list)
    total_atrasos: int = 0
    avance_pct: float = 0.0


class AtrasadosResponse(BaseModel):
    """Response from GET /api/analisis/atrasados."""

    model_config = ConfigDict(extra="forbid")

    items: list[AtrasadoRow]
    total: int


# ── Ranking ────────────────────────────────────────────────────────────────────


class RankingRow(BaseModel):
    """A single entry in the ranking."""

    model_config = ConfigDict(extra="forbid")

    posicion: int
    entrada_padron_id: uuid.UUID
    alumno: str = Field(..., description="Apellidos, Nombre")
    actividades_aprobadas: int
    total_actividades: int
    porcentaje_aprobacion: float


class RankingResponse(BaseModel):
    """Response from GET /api/analisis/ranking."""

    model_config = ConfigDict(extra="forbid")

    items: list[RankingRow]
    total_actividades: int
    total_alumnos: int


# ── Reportes rápidos ───────────────────────────────────────────────────────────


class ReporteRapidoResponse(BaseModel):
    """Response from GET /api/analisis/reportes-rapidos."""

    model_config = ConfigDict(extra="forbid")

    total_alumnos: int
    alumnos_atrasados: int
    actividades_sin_corregir: int
    porcentaje_aprobacion_general: float
    estado: str = Field(
        default="con_datos",
        description='"con_datos" | "sin_datos"',
    )


# ── Notas finales ──────────────────────────────────────────────────────────────


class ActividadNota(BaseModel):
    """A single activity's grade detail."""

    model_config = ConfigDict(extra="forbid")

    nombre: str
    nota: Decimal | None = None
    nota_textual: str | None = None
    aprobado: bool


class NotasFinalesRow(BaseModel):
    """A student's final grade summary."""

    model_config = ConfigDict(extra="forbid")

    entrada_padron_id: uuid.UUID
    alumno: str = Field(..., description="Apellidos, Nombre")
    promedio: float | None = None
    aprobado: bool
    umbral_aplicado: float = 0.60
    actividades: list[ActividadNota] = Field(default_factory=list)


class NotasFinalesResponse(BaseModel):
    """Response from GET /api/analisis/notas-finales."""

    model_config = ConfigDict(extra="forbid")

    items: list[NotasFinalesRow]


# ── Sin corregir (export CSV) ──────────────────────────────────────────────────


class SinCorregirRow(BaseModel):
    """A textual activity delivery without a grade."""

    model_config = ConfigDict(extra="forbid")

    alumno: str = Field(..., description="Apellidos, Nombre")
    actividad: str
    fecha_entrega: date | None = None


# ── Monitor general ────────────────────────────────────────────────────────────


class MonitorGeneralRow(BaseModel):
    """A student's status in the general monitor view."""

    model_config = ConfigDict(extra="forbid")

    entrada_padron_id: uuid.UUID
    alumno: str = Field(..., description="Apellidos, Nombre")
    estado: str = Field(
        ...,
        description='"al_dia" | "atrasado" | "sin_datos"',
    )
    actividades_aprobadas: int = 0
    total_actividades: int = 0
    porcentaje_avance: float | None = 0.0


class MonitorGeneralResponse(BaseModel):
    """Response from GET /api/analisis/monitor-general."""

    model_config = ConfigDict(extra="forbid")

    items: list[MonitorGeneralRow]
    total: int


# ── Monitor seguimiento ────────────────────────────────────────────────────────


class MonitorSeguimientoRow(BaseModel):
    """A student's activity detail in the seguimiento view."""

    model_config = ConfigDict(extra="forbid")

    entrada_padron_id: uuid.UUID
    alumno: str = Field(..., description="Apellidos, Nombre")
    actividad_nombre: str
    nota: Decimal | None = None
    nota_textual: str | None = None
    resultado: str = Field(
        ...,
        description='"aprobado" | "desaprobado"',
    )
    estado_general: str = Field(
        ...,
        description='"al_dia" | "atrasado" | "sin_datos"',
    )


class MonitorSeguimientoResponse(BaseModel):
    """Response from GET /api/analisis/monitor-seguimiento."""

    model_config = ConfigDict(extra="forbid")

    items: list[MonitorSeguimientoRow]
    total: int
