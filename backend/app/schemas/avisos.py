"""Pydantic schemas for Avisos and Acknowledgment endpoints.

All request schemas use extra='forbid' as per project convention.
Response schemas use from_attributes=True for ORM model compatibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Aviso crear ────────────────────────────────────────────────────────────────


class AvisoCrearRequest(BaseModel):
    """Request body for POST /api/avisos — create a new notice."""

    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(..., max_length=200, description="Notice title")
    cuerpo: str = Field(..., description="Notice body text")
    alcance: str = Field(..., description="Audience scope: Global, PorMateria, PorCohorte, PorRol")
    materia_id: uuid.UUID | None = Field(default=None, description="Required if alcance=PorMateria")
    cohorte_id: uuid.UUID | None = Field(default=None, description="Required if alcance=PorCohorte")
    rol_destino: str | None = Field(default=None, max_length=50, description="Required if alcance=PorRol")
    severidad: str = Field(..., description="Severity: Info, Advertencia, Crítico")
    inicio_en: datetime = Field(..., description="Validity window start (UTC)")
    fin_en: datetime = Field(..., description="Validity window end (UTC)")
    orden: int = Field(default=0, description="Display order — lower = higher priority")
    requiere_ack: bool = Field(default=False, description="Whether read acknowledgment is required")


# ── Aviso actualizar ───────────────────────────────────────────────────────────


class AvisoUpdateRequest(BaseModel):
    """Request body for PATCH /api/avisos/{id} — partial update of a notice.

    All fields are optional. Only provided fields will be updated.
    """

    model_config = ConfigDict(extra="forbid")

    titulo: str | None = Field(default=None, max_length=200)
    cuerpo: str | None = None
    alcance: str | None = None
    materia_id: uuid.UUID | None = None
    cohorte_id: uuid.UUID | None = None
    rol_destino: str | None = Field(default=None, max_length=50)
    severidad: str | None = None
    inicio_en: datetime | None = None
    fin_en: datetime | None = None
    orden: int | None = None
    activo: bool | None = None
    requiere_ack: bool | None = None


# ── Aviso response (listado gestión) ───────────────────────────────────────────


class AvisoResponse(BaseModel):
    """Response schema for a single notice in the management list.

    Includes derived acknowledgment counters.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    titulo: str
    alcance: str
    severidad: str
    activo: bool
    inicio_en: datetime
    fin_en: datetime
    orden: int
    requiere_ack: bool
    created_at: datetime | None = None
    total_vistos: int = 0
    total_acks: int = 0


class AvisoListResponse(BaseModel):
    """Response for GET /api/avisos — paginated management list."""

    model_config = ConfigDict(extra="forbid")

    items: list[AvisoResponse]
    total: int


# ── Mis avisos (visualización destinatario) ────────────────────────────────────


class MisAvisoItem(BaseModel):
    """A single notice visible to the authenticated user."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    titulo: str
    cuerpo: str
    severidad: str
    orden: int
    requiere_ack: bool
    ya_ack: bool = False


class MisAvisosResponse(BaseModel):
    """Response for GET /api/avisos/mis-avisos."""

    model_config = ConfigDict(extra="forbid")

    items: list[MisAvisoItem]


# ── Acknowledgment ─────────────────────────────────────────────────────────────


class AckResponse(BaseModel):
    """Response for POST /api/avisos/{id}/ack — acknowledgment created."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    aviso_id: uuid.UUID
    confirmado_at: datetime


class AckItem(BaseModel):
    """A single acknowledgment record in the management view."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: uuid.UUID
    usuario_email: str = ""
    confirmado_at: datetime


class AcksListResponse(BaseModel):
    """Response for GET /api/avisos/{id}/acks — list of acknowledgments."""

    model_config = ConfigDict(extra="forbid")

    items: list[AckItem]
    total: int
