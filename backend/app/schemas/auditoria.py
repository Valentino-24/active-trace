"""Pydantic schemas for Panel de Auditoria y Metricas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AccionesPorDiaItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha: str
    total: int

class AccionesPorDiaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AccionesPorDiaItem]
    total: int


class MetricaDocenteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_id: uuid.UUID
    accion: str
    total: int
    ultima_fecha: datetime | None = None

class MetricasDocenteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[MetricaDocenteItem]
    total: int


class AuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_id: uuid.UUID
    accion: str
    fecha_hora: datetime
    materia_id: uuid.UUID | None = None
    filas_afectadas: int
    detalle: dict | None = None
    ip: str | None = None

class AuditLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[AuditLogItem]
    total: int
