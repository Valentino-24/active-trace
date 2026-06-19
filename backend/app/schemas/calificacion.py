"""Pydantic schemas for Calificacion endpoints.

Covers preview, import, finalizacion, and list operations.
All request schemas use extra='forbid' as per project convention.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Preview schemas ──────────────────────────────────────────────────────────


class PreviewColumn(BaseModel):
    """A detected column from the LMS file."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(..., description="Cleaned column name (without suffix)")
    tipo: Literal["numerica", "textual"] = Field(
        ..., description="RN-01/RN-02 classification"
    )
    max_nota: float | None = Field(
        default=None, description="Max possible grade for this column"
    )


class PreviewRow(BaseModel):
    """A single parsed row from an LMS grade file."""

    model_config = ConfigDict(extra="forbid")

    fila: int
    email: str
    nombre: str
    apellidos: str
    valores: dict[str, Any] = Field(
        default_factory=dict,
        description="Column values keyed by activity name",
    )


class PreviewError(BaseModel):
    """An error encountered while parsing a specific row/column."""

    model_config = ConfigDict(extra="forbid")

    fila: int | None = None
    columna: str | None = None
    mensaje: str


class PreviewResponse(BaseModel):
    """Response from POST /api/calificaciones/preview (no data persisted)."""

    model_config = ConfigDict(extra="forbid")

    columnas: list[PreviewColumn]
    filas: list[PreviewRow]
    errores: list[PreviewError] = Field(default_factory=list)
    total_filas: int


# ── Import schemas ───────────────────────────────────────────────────────────


class NotaAlumno(BaseModel):
    """A single student's grade in an import request."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., min_length=1, max_length=255)
    nota: float | None = Field(default=None)
    nota_textual: str | None = Field(default=None, max_length=100)


class ImportRequest(BaseModel):
    """Request body for POST /api/calificaciones/import."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    actividad_nombre: str = Field(..., min_length=1, max_length=255)
    notas: list[NotaAlumno] = Field(..., max_length=10_000)
    max_nota: float | None = Field(default=None)


class ImportResponse(BaseModel):
    """Response after a successful grade import."""

    model_config = ConfigDict(extra="forbid")

    importadas: int
    aprobadas: int
    reprobadas: int
    errores: list[str] = Field(default_factory=list)


# ── Finalizacion schemas ─────────────────────────────────────────────────────


class FinalizacionRow(BaseModel):
    """A detected delivery without a grade."""

    model_config = ConfigDict(extra="forbid")

    alumno: str
    actividad: str
    estado: Literal["Sin_corregir"] = "Sin_corregir"


class FinalizacionResponse(BaseModel):
    """Response from POST /api/calificaciones/importar-finalizacion."""

    model_config = ConfigDict(extra="forbid")

    items: list[FinalizacionRow]
    total: int


# ── List schemas ─────────────────────────────────────────────────────────────


class CalificacionResponse(BaseModel):
    """Response schema for a single grade record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entrada_padron_id: uuid.UUID
    usuario_id: uuid.UUID | None = None
    actividad_nombre: str
    nota: float | None = None
    nota_textual: str | None = None
    aprobado: bool
    origen: str
    extra_data: dict[str, Any] | None = None
    periodo: str
    created_at: datetime


class CalificacionListResponse(BaseModel):
    """Paginated list of grade records."""

    model_config = ConfigDict(extra="forbid")

    items: list[CalificacionResponse]
    total: int
    skip: int
    limit: int
