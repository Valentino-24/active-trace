"""Cohorte model — a cohort (group of students) within a carrera.

A cohort represents a specific group of students that starts and progresses
through a carrera together. Each cohort belongs to exactly one carrera.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Cohorte(Base, TenantScopedMixin, SoftDeleteMixin):
    """A cohort (group of students) within a carrera.

    Attributes:
        carrera_id: FK to the parent carrera.
        nombre: Short name for the cohort (e.g. '2026-A').
        anio: Academic year (e.g. 2026).
        vig_desde: Start date of validity.
        vig_hasta: End date of validity (null = still open).
        estado: 'activa' | 'inactiva'
    """

    __tablename__ = "cohorte"
    __table_args__ = (
        Index("ix_cohorte_carrera_id", "carrera_id"),
        UniqueConstraint(
            "tenant_id", "carrera_id", "nombre", name="uq_cohorte_tenant_carrera_nombre"
        ),
    )

    carrera_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("carrera.id", ondelete="CASCADE"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    anio: Mapped[int] = mapped_column(Integer, nullable=False)
    vig_desde: Mapped[date] = mapped_column(Date, nullable=False)
    vig_hasta: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="activa"
    )
