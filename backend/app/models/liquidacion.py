"""Liquidacion model — teacher honorarium calculation for a period."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Liquidacion(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "liquidacion"

    cohorte_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), ForeignKey("cohorte.id", ondelete="CASCADE"), nullable=False,
    )
    periodo: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    rol: Mapped[str] = mapped_column(String(50), nullable=False)
    monto_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_plus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    es_nexo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excluido_por_factura: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="Abierta")
