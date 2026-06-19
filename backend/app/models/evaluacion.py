"""Evaluacion model — convocatoria de evaluación/coloquio.

Represents an evaluation or oral exam convocation with matter, cohort,
type, instance, and capacity management via dias_disponibles.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.materia import Materia
    from app.models.cohorte import Cohorte


class TipoEvaluacion(str, enum.Enum):
    """Types of evaluations available in the system.

    Parcial: Mid-term exam
    TP: Practical work
    Coloquio: Oral final exam
    Recuperatorio: Make-up exam
    """

    Parcial = "Parcial"
    TP = "TP"
    Coloquio = "Coloquio"
    Recuperatorio = "Recuperatorio"


class Evaluacion(Base, TenantScopedMixin, SoftDeleteMixin):
    """A convocation for an evaluation/oral exam.

    Attributes:
        materia_id: FK to the subject.
        cohorte_id: FK to the cohort.
        tipo: Type of evaluation (Parcial|TP|Coloquio|Recuperatorio).
        instancia: Human-readable instance name (e.g. "Coloquio Final 2026").
        dias_disponibles: Maximum number of active reservations allowed (cupo).
        activa: Whether the convocation is open for reservations.
    """

    __tablename__ = "evaluacion"
    __table_args__ = (
        Index("ix_evaluacion_activa", "tenant_id", "activa"),
        Index("ix_evaluacion_materia", "tenant_id", "materia_id"),
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
    tipo: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    instancia: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    dias_disponibles: Mapped[int] = mapped_column(
        nullable=False, default=30,
    )
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    materia: Mapped[Materia] = relationship(
        "Materia",
        lazy="selectin",
    )
    cohorte: Mapped[Cohorte] = relationship(
        "Cohorte",
        lazy="selectin",
    )
