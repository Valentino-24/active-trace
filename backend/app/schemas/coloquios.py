"""Pydantic schemas for Coloquios endpoints.

All request schemas use extra='forbid' as per project convention.
Response schemas use from_attributes=True for ORM model compatibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Enums ─────────────────────────────────────────────────────────────────────


TIPO_EVALUACION_VALUES = {"Parcial", "TP", "Coloquio", "Recuperatorio"}


# ── Evaluacion (convocatoria) schemas ─────────────────────────────────────────


class EvaluacionCrearRequest(BaseModel):
    """Request body for POST /api/coloquios — create convocation."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    tipo: str = Field(
        ...,
        description="Tipo de evaluación: Parcial, TP, Coloquio, Recuperatorio",
    )
    instancia: str = Field(
        ..., max_length=500, description="Nombre de la instancia evaluativa",
    )
    dias_disponibles: int = Field(
        default=30, ge=1, description="Cupo máximo de reservas activas",
    )

    @field_validator("tipo")
    @classmethod
    def _validar_tipo(cls, v: str) -> str:
        if v not in TIPO_EVALUACION_VALUES:
            raise ValueError(
                f"Tipo inválido: '{v}'. Debe ser uno de: {', '.join(sorted(TIPO_EVALUACION_VALUES))}"
            )
        return v


class EvaluacionUpdateRequest(BaseModel):
    """Request body for PATCH /api/coloquios/{id} — update convocation."""

    model_config = ConfigDict(extra="forbid")

    activa: bool | None = None
    dias_disponibles: int | None = Field(default=None, ge=1)
    instancia: str | None = Field(default=None, max_length=500)


class EvaluacionResponse(BaseModel):
    """Response schema for a single evaluacion con metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    tipo: str
    instancia: str
    dias_disponibles: int
    activa: bool
    created_at: datetime
    updated_at: datetime


# ── Importar alumnos schemas ──────────────────────────────────────────────────


class ImportarAlumnosRequest(BaseModel):
    """Request body for POST /api/coloquios/{id}/alumnos."""

    model_config = ConfigDict(extra="forbid")

    alumno_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="List of student user IDs to import",
    )


class ImportarAlumnosResponse(BaseModel):
    """Response from importing alumnos to a convocation."""

    model_config = ConfigDict(extra="forbid")

    importados: int
    ya_existentes: int


# ── Reserva schemas ───────────────────────────────────────────────────────────


class ReservaRequest(BaseModel):
    """Request body for POST /api/coloquios/{id}/reservar."""

    model_config = ConfigDict(extra="forbid")

    fecha_hora: datetime = Field(
        ..., description="Date and time of the reserved slot",
    )


class ReservaResponse(BaseModel):
    """Response schema for a single reservation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evaluacion_id: uuid.UUID
    alumno_id: uuid.UUID
    fecha_hora: datetime
    estado: str
    created_at: datetime


# ── Resultado schemas ─────────────────────────────────────────────────────────


class ResultadoUpdateRequest(BaseModel):
    """Request body for PATCH /api/coloquios/resultados/{id}."""

    model_config = ConfigDict(extra="forbid")

    nota_final: str = Field(
        ..., max_length=50, description="Final grade as text (e.g. '8', 'Aprobado')",
    )


class ResultadoResponse(BaseModel):
    """Response schema for a grade result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evaluacion_id: uuid.UUID
    alumno_id: uuid.UUID
    nota_final: str | None = None
    registrada_at: datetime | None = None
    created_at: datetime


# ── List / Metrics / Agenda / Registro schemas ────────────────────────────────


class ConvocatoriaDisponibleItem(BaseModel):
    """A convocation visible to a student (for listar_disponibles)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    materia_id: uuid.UUID
    instancia: str
    tipo: str
    dias_disponibles: int
    tiene_reserva: bool = False


class ConvocatoriaDisponibleResponse(BaseModel):
    """Response for GET /api/coloquios/disponibles."""

    model_config = ConfigDict(extra="forbid")

    items: list[ConvocatoriaDisponibleItem]


class ConvocatoriaListItem(BaseModel):
    """A convocation item in the list with derived metrics."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    materia_id: uuid.UUID
    instancia: str
    tipo: str
    dias_disponibles: int
    activa: bool
    convocados: int = 0
    reservas_activas: int = 0
    cupo_disponible: int = 0
    created_at: datetime | None = None


class ConvocatoriaListResponse(BaseModel):
    """Response for GET /api/coloquios."""

    model_config = ConfigDict(extra="forbid")

    items: list[ConvocatoriaListItem]
    total: int


class MetricasResponse(BaseModel):
    """Response for GET /api/coloquios/metricas."""

    model_config = ConfigDict(extra="forbid")

    total_alumnos_cargados: int = 0
    instancias_activas: int = 0
    reservas_activas: int = 0
    notas_registradas: int = 0


class AgendaItem(BaseModel):
    """A single reservation in the agenda view."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    alumno: str = ""
    materia: str = ""
    fecha_hora: datetime | None = None
    evaluacion: str = ""
    estado: str = ""


class AgendaResponse(BaseModel):
    """Response for GET /api/coloquios/agenda."""

    model_config = ConfigDict(extra="forbid")

    items: list[AgendaItem]


class RegistroItem(BaseModel):
    """A single grade record in the academic registry."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    alumno: str = ""
    materia: str = ""
    instancia: str = ""
    nota_final: str | None = None
    registrada_at: datetime | None = None


class RegistroResponse(BaseModel):
    """Response for GET /api/coloquios/registro."""

    model_config = ConfigDict(extra="forbid")

    items: list[RegistroItem]


class MisReservasItem(BaseModel):
    """A reservation as seen by the student."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    evaluacion_id: uuid.UUID
    materia: str = ""
    instancia: str = ""
    fecha_hora: datetime | None = None
    estado: str = ""
    created_at: datetime | None = None


class MisReservasResponse(BaseModel):
    """Response for GET /api/coloquios/mis-reservas."""

    model_config = ConfigDict(extra="forbid")

    items: list[MisReservasItem]
