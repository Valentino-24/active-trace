"""Schemas for Perfil and Inbox."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PerfilUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, max_length=255)

class PerfilResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str | None = None
    cuil: str | None = None


class MensajeEnviarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destinatario_id: uuid.UUID
    asunto: str = Field(..., max_length=255)
    texto: str

class MensajeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    remitente_id: uuid.UUID
    destinatario_id: uuid.UUID
    asunto: str
    texto: str
    leido: bool
    leido_at: datetime | None = None
    created_at: datetime | None = None

class MensajeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[MensajeResponse]
    total: int
