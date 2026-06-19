"""SalarioBase model — base salary grid by role with temporal validity."""

from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class SalarioBase(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "salario_base"

    rol: Mapped[str] = mapped_column(String(50), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    desde: Mapped[date_type] = mapped_column(Date, nullable=False)
    hasta: Mapped[date_type | None] = mapped_column(Date, nullable=True, default=None)
