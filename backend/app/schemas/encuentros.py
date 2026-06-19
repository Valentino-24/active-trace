"""Pydantic schemas for Encuentros endpoints.

All request schemas use extra='forbid' as per project convention.
Response schemas use from_attributes=True for ORM compatibility.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlotCrearRequest(BaseModel):
    """Request body for POST /api/encuentros/slots.

    Two mutually exclusive modes per RN-13:
        - Recurrent: cant_semanas > 0, fecha_unica = None
        - Single date: cant_semanas = 0, fecha_unica = NOT None
    """

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    titulo: str = Field(..., min_length=1, max_length=255)
    hora: str = Field(..., min_length=1, max_length=10)
    dia_semana: str = Field(..., min_length=1, max_length=15)
    fecha_inicio: date
    cant_semanas: int = Field(default=0, ge=0)
    fecha_unica: date | None = Field(default=None)
    meet_url: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def _validar_modo(self) -> "SlotCrearRequest":
        """Validate mutually exclusive modes (RN-13)."""
        if self.cant_semanas > 0 and self.fecha_unica is not None:
            raise ValueError(
                "Modo ambiguo: no se puede especificar cant_semanas y fecha_unica simultáneamente"
            )
        if self.cant_semanas == 0 and self.fecha_unica is None:
            raise ValueError(
                "Modo inválido: debe especificar cant_semanas > 0 o fecha_unica"
            )
        return self


class InstanciaUpdateRequest(BaseModel):
    """Request body for PATCH /api/encuentros/instancias/{id}.

    All fields are optional — only provided fields are updated.
    """

    model_config = ConfigDict(extra="forbid")

    estado: str | None = Field(default=None, max_length=20)
    meet_url: str | None = Field(default=None, max_length=1024)
    video_url: str | None = Field(default=None, max_length=1024)
    comentario: str | None = Field(default=None)


class SlotResponse(BaseModel):
    """Response schema for a SlotEncuentro."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    materia_id: uuid.UUID
    titulo: str
    hora: str
    dia_semana: str
    fecha_inicio: date
    cant_semanas: int
    fecha_unica: date | None = None
    meet_url: str | None = None
    vig_desde: date | None = None
    vig_hasta: date | None = None
    created_at: datetime


class InstanciaResponse(BaseModel):
    """Response schema for an InstanciaEncuentro."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slot_id: uuid.UUID | None = None
    materia_id: uuid.UUID
    fecha: date
    hora: str
    titulo: str
    estado: str
    meet_url: str | None = None
    video_url: str | None = None
    comentario: str | None = None
    created_at: datetime


class SlotConInstanciasResponse(BaseModel):
    """Response for slot creation (slot + generated instances)."""

    model_config = ConfigDict(extra="forbid")

    slot: SlotResponse
    instancias: list[InstanciaResponse]
    total_instancias: int


class InstanciaListResponse(BaseModel):
    """Response for instance listing."""

    model_config = ConfigDict(extra="forbid")

    items: list[InstanciaResponse]
    total: int


class SlotListResponse(BaseModel):
    """Response for slot listing."""

    model_config = ConfigDict(extra="forbid")

    items: list[SlotResponse]
    total: int


class HtmlResponse(BaseModel):
    """Response containing generated HTML block."""

    model_config = ConfigDict(extra="forbid")

    html: str
