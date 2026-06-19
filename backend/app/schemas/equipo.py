"""Pydantic schemas for equipo (team) operations.

High-level schemas for bulk assignment, cloning, vigency management,
and team listing. Used exclusively by the /api/equipos router.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.asignacion import AsignacionDocenteInfo

# ── AsignacionMasiva (bulk create) ────────────────────────────────────────


class AsignacionItem(BaseModel):
    """Single assignment entry within a bulk request."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: uuid.UUID
    rol: str = Field(max_length=50)
    responsable_id: uuid.UUID | None = None


class AsignacionMasivaRequest(BaseModel):
    """Bulk assignment request — common context + list of assignees."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID
    comisiones: list[str] = Field(default_factory=list)
    desde: date
    hasta: date | None = None
    asignaciones: list[AsignacionItem]


class AsignacionMasivaResponse(BaseModel):
    """Response for a bulk assignment operation."""

    model_config = ConfigDict(extra="forbid")

    creadas: int
    items: list[AsignacionDocenteInfo]


# ── CloneEquipo ───────────────────────────────────────────────────────────


class CloneEquipoOrigen(BaseModel):
    """Source context for cloning."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID


class CloneEquipoDestino(BaseModel):
    """Destination context for cloning."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID


class CloneEquipoRequest(BaseModel):
    """Clone equipo request — copy assignments from origin to destination."""

    model_config = ConfigDict(extra="forbid")

    origen: CloneEquipoOrigen
    destino: CloneEquipoDestino
    incluir_roles: list[str] | None = None


class CloneEquipoResponse(BaseModel):
    """Response for a clone operation."""

    model_config = ConfigDict(extra="forbid")

    clonadas: int
    items: list[uuid.UUID]


# ── Vigencia (bulk update) ────────────────────────────────────────────────


class VigenciaRequest(BaseModel):
    """Bulk vigency update request — filters + new dates."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID | None = None
    carrera_id: uuid.UUID | None = None
    cohorte_id: uuid.UUID | None = None
    rol: str | None = Field(default=None, max_length=50)
    nuevo_desde: date | None = None
    nuevo_hasta: date | None = None
    confirmar: bool = False


class VigenciaResponse(BaseModel):
    """Response for a vigency update operation."""

    model_config = ConfigDict(extra="forbid")

    actualizadas: int
    items: list[uuid.UUID]


# ── EquipoListResponse ────────────────────────────────────────────────────


class EquipoListResponse(BaseModel):
    """Paginated list response for equipo endpoints."""

    model_config = ConfigDict(extra="forbid")

    items: list[AsignacionDocenteInfo]
    total: int
