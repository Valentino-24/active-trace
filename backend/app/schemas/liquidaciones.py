"""Pydantic schemas for Liquidaciones, Salarios y Facturas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ── SalarioBase ──────────────────────────────────────────────────────────────

class SalarioBaseCrearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rol: str = Field(..., max_length=50)
    monto: Decimal
    desde: date
    hasta: date | None = None

class SalarioBaseUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monto: Decimal | None = None
    hasta: date | None = None

class SalarioBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rol: str
    monto: Decimal
    desde: date
    hasta: date | None = None


# ── SalarioPlus ──────────────────────────────────────────────────────────────

class SalarioPlusCrearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grupo: str = Field(..., max_length=50)
    rol: str = Field(..., max_length=50)
    descripcion: str | None = Field(default=None, max_length=255)
    monto: Decimal
    desde: date
    hasta: date | None = None

class SalarioPlusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    grupo: str
    rol: str
    descripcion: str | None = None
    monto: Decimal
    desde: date
    hasta: date | None = None


# ── Liquidacion ──────────────────────────────────────────────────────────────

class LiquidacionCalcularRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cohorte_id: uuid.UUID
    periodo: str = Field(..., max_length=20)

class LiquidacionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cohorte_id: uuid.UUID
    periodo: str
    usuario_id: uuid.UUID
    rol: str
    monto_base: Decimal
    monto_plus: Decimal
    total: Decimal
    es_nexo: bool
    excluido_por_factura: bool
    estado: str

class LiquidacionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[LiquidacionResponse]
    total: int


# ── Factura ──────────────────────────────────────────────────────────────────

class FacturaCrearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usuario_id: uuid.UUID
    periodo: str = Field(..., max_length=20)
    detalle: str
    referencia_archivo: str | None = Field(default=None, max_length=500)

class FacturaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    usuario_id: uuid.UUID
    periodo: str
    detalle: str
    referencia_archivo: str | None = None
    estado: str
    abonada_at: datetime | None = None
    cargada_at: datetime | None = None
