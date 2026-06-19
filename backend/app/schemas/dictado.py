"""Pydantic schemas for Dictado entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DictadoCreate(BaseModel):
    """Request schema for creating a new dictado."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID


class DictadoUpdate(BaseModel):
    """Request schema for updating an existing dictado."""

    model_config = ConfigDict(extra="forbid")

    estado: Optional[str] = Field(default=None, max_length=20)


class DictadoResponse(BaseModel):
    """Response schema for a dictado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID
    estado: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class DictadoListResponse(BaseModel):
    """Response schema for paginated list of dictados."""

    model_config = ConfigDict(extra="forbid")

    items: list[DictadoResponse]
    total: int
