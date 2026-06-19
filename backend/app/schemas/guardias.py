"""Pydantic schemas for Guardias endpoints.

All request schemas use extra='forbid' as per project convention.
Response schemas use from_attributes=True for ORM compatibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GuardiaCrearRequest(BaseModel):
    """Request body for POST /api/guardias."""

    model_config = ConfigDict(extra="forbid")

    asignacion_id: uuid.UUID
    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID
    dia: str = Field(..., min_length=1, max_length=15)
    horario: str = Field(..., min_length=1, max_length=20)
    comentarios: str | None = Field(default=None)


class GuardiaUpdateRequest(BaseModel):
    """Request body for PATCH /api/guardias/{id}.

    All fields are optional.
    """

    model_config = ConfigDict(extra="forbid")

    estado: str | None = Field(default=None, max_length=20)
    comentarios: str | None = Field(default=None)


class GuardiaResponse(BaseModel):
    """Response schema for a Guardia record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    asignacion_id: uuid.UUID
    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID
    dia: str
    horario: str
    estado: str
    comentarios: str | None = None
    creada_at: datetime
    created_at: datetime
    updated_at: datetime


class GuardiaListResponse(BaseModel):
    """Response for guardia listing."""

    model_config = ConfigDict(extra="forbid")

    items: list[GuardiaResponse]
    total: int
