"""Factura model — billing document for teachers who invoice."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Factura(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "factura"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    periodo: Mapped[str] = mapped_column(String(20), nullable=False)
    detalle: Mapped[str] = mapped_column(Text, nullable=False)
    referencia_archivo: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)
    tamano_kb: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True, default=None)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="Pendiente")
    cargada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    abonada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )
