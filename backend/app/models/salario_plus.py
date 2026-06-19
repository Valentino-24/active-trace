"""SalarioPlus model — salary supplement by group and role."""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class SalarioPlus(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "salario_plus"

    grupo: Mapped[str] = mapped_column(String(50), nullable=False)
    rol: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    desde: Mapped[date_type] = mapped_column(Date, nullable=False)
    hasta: Mapped[date_type | None] = mapped_column(Date, nullable=True, default=None)
