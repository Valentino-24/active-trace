"""Pydantic schemas for Programas and Fechas Academicas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Programa ─────────────────────────────────────────────────────────────────


class ProgramaCrearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID
    titulo: str = Field(..., max_length=255)
    referencia_archivo: str | None = Field(default=None, max_length=500)


class ProgramaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titulo: str | None = Field(default=None, max_length=255)
    referencia_archivo: str | None = Field(default=None, max_length=500)


class ProgramaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    materia_id: uuid.UUID
    carrera_id: uuid.UUID
    cohorte_id: uuid.UUID
    titulo: str
    referencia_archivo: str | None = None
    cargado_at: datetime | None = None
    created_at: datetime | None = None


class ProgramaListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ProgramaResponse]
    total: int


# ── Fecha Academica ──────────────────────────────────────────────────────────


class FechaCrearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    tipo: str = Field(..., max_length=20)
    numero: int
    periodo: str = Field(..., max_length=50)
    fecha: date
    titulo: str = Field(..., max_length=255)


class FechaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: str | None = Field(default=None, max_length=20)
    numero: int | None = None
    periodo: str | None = Field(default=None, max_length=50)
    fecha: date | None = None
    titulo: str | None = Field(default=None, max_length=255)


class FechaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    tipo: str
    numero: int
    periodo: str
    fecha: date
    titulo: str
    created_at: datetime | None = None


class FechaListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[FechaResponse]
    total: int
