"""Pydantic schemas for Tareas and Comentarios endpoints.

All request schemas use extra='forbid' as per project convention.
Response schemas use from_attributes=True for ORM model compatibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Tarea crear ──────────────────────────────────────────────────────────────


class TareaCrearRequest(BaseModel):
    """Request body for POST /api/tareas — create a new task."""

    model_config = ConfigDict(extra="forbid")

    asignado_a: uuid.UUID = Field(..., description="User assigned to the task")
    materia_id: uuid.UUID | None = Field(default=None, description="Optional related materia")
    descripcion: str = Field(..., description="Task description")
    contexto_id: uuid.UUID | None = Field(default=None, description="External context reference")


# ── Tarea estado update ──────────────────────────────────────────────────────


class TareaEstadoUpdateRequest(BaseModel):
    """Request body for PATCH /api/tareas/{id}/estado."""

    model_config = ConfigDict(extra="forbid")

    estado: str = Field(..., description="New state: Pendiente, EnProgreso, Resuelta, Cancelada")


# ── Tarea reasignar ──────────────────────────────────────────────────────────


class TareaReasignarRequest(BaseModel):
    """Request body for PATCH /api/tareas/{id}/asignar."""

    model_config = ConfigDict(extra="forbid")

    asignado_a: uuid.UUID = Field(..., description="New user to assign the task to")


# ── Tarea response ───────────────────────────────────────────────────────────


class TareaResponse(BaseModel):
    """Response schema for a single task (admin/management view)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    materia_id: uuid.UUID | None = None
    asignado_a: uuid.UUID
    asignado_por: uuid.UUID
    estado: str
    descripcion: str
    contexto_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TareaMiaResponse(BaseModel):
    """Response schema for a task in 'mis tareas' view — includes ultimo_comentario."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    materia_id: uuid.UUID | None = None
    asignado_por: uuid.UUID
    estado: str
    descripcion: str
    ultimo_comentario: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TareaListResponse(BaseModel):
    """Paginated response for task listings."""

    model_config = ConfigDict(extra="forbid")

    items: list[TareaResponse | TareaMiaResponse]
    total: int


# ── Comentario ───────────────────────────────────────────────────────────────


class ComentarioCrearRequest(BaseModel):
    """Request body for POST /api/tareas/{id}/comentarios."""

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(..., min_length=1, description="Comment text")


class ComentarioResponse(BaseModel):
    """Response schema for a single comment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tarea_id: uuid.UUID
    autor_id: uuid.UUID
    texto: str
    creado_at: datetime


class ComentarioListResponse(BaseModel):
    """Paginated response for comment listings."""

    model_config = ConfigDict(extra="forbid")

    items: list[ComentarioResponse]
    total: int
