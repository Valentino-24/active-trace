"""Pydantic schemas for Cohorte entity."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CohorteCreate(BaseModel):
    """Request schema for creating a new cohorte."""

    model_config = ConfigDict(extra="forbid")

    carrera_id: uuid.UUID
    nombre: str = Field(max_length=100)
    anio: int
    vig_desde: date
    vig_hasta: Optional[date] = None


class CohorteUpdate(BaseModel):
    """Request schema for updating an existing cohorte."""

    model_config = ConfigDict(extra="forbid")

    nombre: Optional[str] = Field(default=None, max_length=100)
    anio: Optional[int] = None
    vig_desde: Optional[date] = None
    vig_hasta: Optional[date] = None
    estado: Optional[str] = Field(default=None, max_length=20)


class CohorteResponse(BaseModel):
    """Response schema for a cohorte."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    carrera_id: uuid.UUID
    nombre: str
    anio: int
    vig_desde: date
    vig_hasta: Optional[date] = None
    estado: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class CohorteListResponse(BaseModel):
    """Response schema for paginated list of cohortes."""

    model_config = ConfigDict(extra="forbid")

    items: list[CohorteResponse]
    total: int
