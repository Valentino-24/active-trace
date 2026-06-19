"""Pydantic schemas for Padron (student roster import) endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Preview schemas ──────────────────────────────────────────────────────────


class PreviewRow(BaseModel):
    """A single parsed row from a padron file preview."""

    model_config = ConfigDict(extra="forbid")

    fila: int
    nombre: str
    apellidos: str
    email: str
    comision: str | None = None
    regional: str | None = None


class PreviewError(BaseModel):
    """An error found while parsing a specific row."""

    model_config = ConfigDict(extra="forbid")

    fila: int
    campo: str
    mensaje: str


class PreviewResponse(BaseModel):
    """Response from the preview endpoint (no data is persisted)."""

    model_config = ConfigDict(extra="forbid")

    total_filas: int
    columnas_detectadas: list[str]
    filas: list[PreviewRow]
    errores: list[PreviewError] = Field(default_factory=list)


# ── Import request/response schemas ─────────────────────────────────────────


class FilaImport(BaseModel):
    """A single student row in an import request."""

    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=255)
    apellidos: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1, max_length=255)
    comision: str | None = Field(default=None, max_length=50)
    regional: str | None = Field(default=None, max_length=255)


class ImportRequest(BaseModel):
    """Request body for confirming a padron import."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    filas: list[FilaImport] = Field(max_length=10_000)


class ImportResponse(BaseModel):
    """Response after successfully importing a padron version."""

    model_config = ConfigDict(extra="forbid")

    version_id: uuid.UUID
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    total_entradas: int
    total_sin_usuario: int
    fecha: datetime
    modo: str


# ── Moodle sync schemas ──────────────────────────────────────────────────────


class MoodleSyncRequest(BaseModel):
    """Request body for triggering a Moodle WS sync."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    cohorte_id: uuid.UUID


# ── Vaciar schemas ───────────────────────────────────────────────────────────


class VaciarResponse(BaseModel):
    """Response after soft-deleting padron data for a materia."""

    model_config = ConfigDict(extra="forbid")

    mensaje: str
    materia_id: uuid.UUID
    versiones_desactivadas: int
    entradas_eliminadas: int


# ── Version/entrada response schemas ────────────────────────────────────────


class CargadoPorInfo(BaseModel):
    """Minimal user info for version metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str = Field(validation_alias="display_name")


class VersionPadronResponse(BaseModel):
    """Response schema for a padron version (list or detail)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    activa: bool
    total_entradas: int = Field(default=0)
    total_sin_usuario: int = Field(default=0)
    cargado_por: CargadoPorInfo
    cargado_at: datetime
    modo: str


class VersionPadronListResponse(BaseModel):
    """Response schema for paginated list of versions."""

    model_config = ConfigDict(extra="forbid")

    items: list[VersionPadronResponse]
    total: int


class EntradaPadronResponse(BaseModel):
    """Response schema for a single padron entry.

    NOTE: email is NOT returned — only the hash, for PII protection.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    apellidos: str
    email_hash: str
    comision: str | None = None
    regional: str | None = None
    tiene_usuario: bool = Field(default=False)


class VersionPadronDetailResponse(BaseModel):
    """Response schema for a version with its entries."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    materia_id: uuid.UUID
    cohorte_id: uuid.UUID
    activa: bool
    cargado_por: CargadoPorInfo
    cargado_at: datetime
    modo: str
    entradas: list[EntradaPadronResponse]
    total_entradas: int
