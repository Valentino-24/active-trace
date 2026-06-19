"""Calificacion model — individual grade records imported from LMS.

Each row represents a grade for one student in one activity within a
specific (materia, cohorte, asignacion) context. Grades can be numeric
(columns ending in (Real) — RN-01) or textual (RN-02). The `aprobado`
field is computed at insert/update time against the effective UmbralMateria.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.padron import EntradaPadron
    from app.models.user import User


class Calificacion(Base, TenantScopedMixin, SoftDeleteMixin):
    """An individual grade record for a student in a specific activity.

    Attributes:
        entrada_padron_id: FK to the matched EntradaPadron.
        materia_id: FK to Materia.
        cohorte_id: FK to Cohorte.
        asignacion_id: FK to Asignacion (the teaching assignment that
            imported the grade).
        usuario_id: Denormalized FK to User from the matched student
            (nullable — enables queries without JOIN to entrada_padron).
        actividad_nombre: Name of the activity/assignment (e.g. "TP1").
        nota: Numeric grade value (nullable — RN-01).
        nota_textual: Textual grade value (nullable — RN-02).
        aprobado: Whether the grade meets the passing threshold
            (computed at insert/update time).
        origen: Source — 'Importado' or 'Manual'.
        extra_data: JSONB with extra info (e.g. max_nota for the activity).
        periodo: Period identifier (e.g. "2026-A").
    """

    __tablename__ = "calificacion"
    __table_args__ = (
        Index("ix_calificacion_materia_cohorte", "materia_id", "cohorte_id"),
        Index("ix_calificacion_asignacion", "asignacion_id"),
        CheckConstraint(
            "origen IN ('Importado', 'Manual')",
            name="ck_calificacion_origen",
        ),
    )

    entrada_padron_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("entrada_padron.id", ondelete="CASCADE"),
        nullable=False,
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
    asignacion_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("asignacion.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    actividad_nombre: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    nota: Mapped[float | None] = mapped_column(
        # Using Float instead of Decimal for simplicity; metadata stores max_nota.
        # The (Real) column from LMS maps to a numeric value here.
        nullable=True, default=None,
    )
    nota_textual: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None,
    )
    aprobado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    origen: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Importado",
    )
    extra_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None,
    )
    periodo: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    entrada_padron: Mapped[EntradaPadron] = relationship(
        "EntradaPadron",
        lazy="selectin",
    )
    usuario: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[usuario_id],
        lazy="selectin",
    )
