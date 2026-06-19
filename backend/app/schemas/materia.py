"""Pydantic schemas for Materia entity."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MateriaCreate(BaseModel):
    """Request schema for creating a new materia."""

    model_config = ConfigDict(extra="forbid")

    codigo: str = Field(max_length=20)
    nombre: str = Field(max_length=255)


class MateriaUpdate(BaseModel):
    """Request schema for updating an existing materia."""

    model_config = ConfigDict(extra="forbid")

    codigo: Optional[str] = Field(default=None, max_length=20)
    nombre: Optional[str] = Field(default=None, max_length=255)
    estado: Optional[str] = Field(default=None, max_length=20)


class MateriaResponse(BaseModel):
    """Response schema for a materia."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    codigo: str
    nombre: str
    estado: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class MateriaListResponse(BaseModel):
    """Response schema for paginated list of materias."""

    model_config = ConfigDict(extra="forbid")

    items: list[MateriaResponse]
    total: int
