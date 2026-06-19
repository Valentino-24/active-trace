"""Pydantic schemas for Comunicaciones endpoints.

All request schemas use extra='forbid' as per project convention.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ── Preview schemas ──────────────────────────────────────────────────────────


class DestinatarioPreview(BaseModel):
    """Recipient data for template preview."""

    model_config = ConfigDict(extra="forbid")

    nombre: str
    apellido: str
    materia: str = Field(default="")
    comision: str = Field(default="")
    nombre_profesor: str = Field(default="")


class PreviewRequest(BaseModel):
    """Request body for POST /api/comunicaciones/preview."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    asunto_template: str
    cuerpo_template: str
    destinatarios: list[DestinatarioPreview]


class PreviewItem(BaseModel):
    """A single preview item per recipient."""

    model_config = ConfigDict(extra="forbid")

    destinatario_masked: str = Field(
        ..., description="Masked email (e.g. j***@test.com)"
    )
    asunto_rendered: str
    cuerpo_rendered: str


class PreviewResponse(BaseModel):
    """Response from POST /api/comunicaciones/preview (no data persisted)."""

    model_config = ConfigDict(extra="forbid")

    items: list[PreviewItem]
    total: int


# ── Enviar schemas ───────────────────────────────────────────────────────────


class EnviarRequest(BaseModel):
    """Request body for POST /api/comunicaciones/enviar."""

    model_config = ConfigDict(extra="forbid")

    materia_id: uuid.UUID
    asunto_template: str
    cuerpo_template: str
    requiere_aprobacion: bool = Field(default=True)


class ComunicacionResponse(BaseModel):
    """Response schema for a single communication record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado: str
    asunto: str
    destinatario_masked: str
    lote_id: uuid.UUID | None = None
    materia_id: uuid.UUID
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _fill_masked(cls, data: Any) -> Any:
        """Auto-fill destinatario_masked when loading from ORM model.

        The ORM model stores the encrypted email in `destinatario`, but
        does not have a `destinatario_masked` field. This validator checks
        if an ORM model or dict was passed without `destinatario_masked`
        and creates a generic masked placeholder.
        """
        if isinstance(data, dict) and "destinatario_masked" not in data:
            if "destinatario" in data:
                raw = data["destinatario"]
                # Mask the encrypted text for safety
                data["destinatario_masked"] = raw[:4] + "***" if len(raw) > 4 else "***"
        elif hasattr(data, "destinatario") and not hasattr(data, "destinatario_masked"):
            raw = data.destinatario
            data.destinatario_masked = raw[:4] + "***" if len(raw) > 4 else "***"
        return data


class LoteResponse(BaseModel):
    """Response for batch operations (enviar, aprobar, cancelar)."""

    model_config = ConfigDict(extra="forbid")

    lote_id: uuid.UUID
    total: int
    estados: dict[str, int] = Field(default_factory=dict)
    created_at: datetime | None = None
    aprobado_por: str | None = None


class EstadisticasResponse(BaseModel):
    """Stats by estado for a materia."""

    model_config = ConfigDict(extra="forbid")

    pendientes: int = 0
    enviando: int = 0
    enviados: int = 0
    fallidos: int = 0
    cancelados: int = 0


# ── Aprobacion schemas ───────────────────────────────────────────────────────


class AprobarRequest(BaseModel):
    """Request body for approval/rejection."""

    model_config = ConfigDict(extra="forbid")

    aprobado: bool = Field(default=True)
    comentario: str | None = Field(default=None, max_length=500)
