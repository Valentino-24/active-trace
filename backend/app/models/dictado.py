"""Dictado model — a teaching instance of a materia in a carrera × cohorte.

Dictado represents the actual teaching of a subject (materia) in a specific
carrera and cohorte. This is the entity that carries grades, assignments,
and teaching teams.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Dictado(Base, TenantScopedMixin, SoftDeleteMixin):
    """A teaching instance of a materia in a carrera × cohorte.

    Attributes:
        materia_id: FK to the subject (materia).
        carrera_id: FK to the degree programme (carrera).
        cohorte_id: FK to the cohort.
        estado: 'activo' | 'inactivo'
    """

    __tablename__ = "dictado"
    __table_args__ = (
        Index("ix_dictado_materia_id", "materia_id"),
        Index("ix_dictado_carrera_id", "carrera_id"),
        Index("ix_dictado_cohorte_id", "cohorte_id"),
        UniqueConstraint(
            "tenant_id", "materia_id", "carrera_id", "cohorte_id",
            name="uq_dictado_unique",
        ),
    )

    materia_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    carrera_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("carrera.id", ondelete="CASCADE"),
        nullable=False,
    )
    cohorte_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("cohorte.id", ondelete="CASCADE"),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="activo"
    )
