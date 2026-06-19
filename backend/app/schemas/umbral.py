"""Pydantic schemas for UmbralMateria endpoints.

Covers list and update operations. extra='forbid' on request schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UmbralResponse(BaseModel):
    """Response schema for a single umbral."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    asignacion_id: uuid.UUID | None = None
    umbral_pct: float
    valores_aprobatorios: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class UmbralUpdateRequest(BaseModel):
    """Request body for PUT /api/umbrales/{id}.

    At least one of umbral_pct or valores_aprobatorios must be provided.
    """

    model_config = ConfigDict(extra="forbid")

    umbral_pct: float | None = Field(default=None, ge=0.0, le=1.0)
    valores_aprobatorios: list[str] | None = None


class UmbralListResponse(BaseModel):
    """Response schema for list of umbrales."""

    model_config = ConfigDict(extra="forbid")

    items: list[UmbralResponse]
