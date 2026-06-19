"""Pydantic schemas for Asignacion entity."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AsignacionCreate(BaseModel):
    """Request schema for creating a new asignacion."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: uuid.UUID
    rol: str = Field(max_length=50)
    materia_id: Optional[uuid.UUID] = None
    carrera_id: Optional[uuid.UUID] = None
    cohorte_id: Optional[uuid.UUID] = None
    comisiones: list[str] = Field(default_factory=list)
    responsable_id: Optional[uuid.UUID] = None
    desde: date
    hasta: Optional[date] = None


class AsignacionResponse(BaseModel):
    """Response schema for an asignacion."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    usuario_id: uuid.UUID
    rol: str
    materia_id: uuid.UUID | None = None
    carrera_id: uuid.UUID | None = None
    cohorte_id: uuid.UUID | None = None
    comisiones: list[str]
    responsable_id: uuid.UUID | None = None
    desde: date
    hasta: date | None = None
    estado_vigencia: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class AsignacionListResponse(BaseModel):
    """Response schema for paginated list of asignaciones."""

    model_config = ConfigDict(extra="forbid")

    items: list[AsignacionResponse]
    total: int


# ── Nested info schemas for expanded equipo responses ─────────────────────


class UsuarioInfo(BaseModel):
    """Minimal user info for equipo responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str = Field(validation_alias="display_name")
    email: str


class MateriaInfo(BaseModel):
    """Minimal materia info for equipo responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str


class CarreraInfo(BaseModel):
    """Minimal carrera info for equipo responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str


class CohorteInfo(BaseModel):
    """Minimal cohorte info for equipo responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str


class ResponsableInfo(BaseModel):
    """Minimal responsable (user) info for equipo responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str = Field(validation_alias="display_name")


class AsignacionDocenteInfo(BaseModel):
    """Expanded response schema with nested relations for equipo views.

    Used by GET /api/equipos, GET /api/equipos/mi-equipo,
    and POST /api/equipos/asignacion-masiva response items.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario: UsuarioInfo
    materia: MateriaInfo | None = None
    carrera: CarreraInfo | None = None
    cohorte: CohorteInfo | None = None
    comisiones: list[str]
    rol: str
    desde: date
    hasta: date | None = None
    responsable: ResponsableInfo | None = None
    estado_vigencia: str
