"""FechaAcademica model — scheduled evaluation dates.

Each FechaAcademica represents a scheduled exam, practical work,
colloquium, or makeup exam for a materia in a specific cohort.
Part of F5.4 — Gestion de fechas de evaluaciones.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date as date_type

from sqlalchemy import Date, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class TipoFecha(str, enum.Enum):
    """Types of academic evaluation dates."""

    Parcial = "Parcial"
    TP = "TP"
    Coloquio = "Coloquio"
    Recuperatorio = "Recuperatorio"


class FechaAcademica(Base, TenantScopedMixin, SoftDeleteMixin):
    """A scheduled evaluation date for a materia in a cohort.

    Attributes:
        materia_id: FK to Materia.
        cohorte_id: FK to Cohorte (carrera is inferred from cohorte).
        tipo: Evaluation type (Parcial|TP|Coloquio|Recuperatorio).
        numero: Instance number (e.g., 1st partial, 2nd partial).
        periodo: Academic period string (e.g., "2025-1").
        fecha: Scheduled date.
        titulo: Descriptive title.
    """

    __tablename__ = "fecha_academica"
    __table_args__ = (
        Index("ix_fecha_academica_materia", "materia_id", "cohorte_id"),
        Index("ix_fecha_academica_periodo", "periodo"),
    )

    materia_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    cohorte_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("cohorte.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha: Mapped[date_type] = mapped_column(Date, nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
