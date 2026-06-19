"""UmbralMateria model — passing threshold configuration per teaching assignment.

Defines the criterion for determining whether a grade counts as "approved"
(aprobado). Inheritance chain follows RN-03:
    1. Specific umbral for (materia, cohorte, asignacion_id)
    2. Default umbral for (materia, cohorte, asignacion_id IS NULL)
    3. Hardcoded default: umbral_pct=0.60, no values_aprobatorios
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class UmbralMateria(Base, TenantScopedMixin, SoftDeleteMixin):
    """Passing threshold configuration for a teaching assignment.

    Attributes:
        materia_id: FK to Materia.
        cohorte_id: FK to Cohorte.
        asignacion_id: FK to Asignacion (nullable — NULL means
            "default for this materia/cohorte").
        umbral_pct: Minimum percentage of max_nota to pass (e.g. 0.60).
        valores_aprobatorios: List of textual values considered passing
            (e.g. ["Satisfactorio", "Supera lo esperado"]).
    """

    __tablename__ = "umbral_materia"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "materia_id", "cohorte_id", "asignacion_id",
            name="uq_umbral_materia_asignacion",
        ),
        Index("ix_umbral_materia_materia_cohorte", "materia_id", "cohorte_id"),
        CheckConstraint(
            "umbral_pct >= 0 AND umbral_pct <= 1",
            name="ck_umbral_materia_pct",
        ),
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
    asignacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("asignacion.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    umbral_pct: Mapped[float] = mapped_column(
        # Float for simplicity; default 0.60 (60%)
        nullable=False, default=0.600,
    )
    valores_aprobatorios: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        default=None,
    )
