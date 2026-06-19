"""ResultadoEvaluacion model — grade result for a student in an evaluation.

Created when a student is imported into an evaluation (nota_final=NULL).
The grade is filled in later by the professor/coordinator.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.user import User


class ResultadoEvaluacion(Base, TenantScopedMixin, SoftDeleteMixin):
    """Grade result for a student in an evaluation.

    Attributes:
        evaluacion_id: FK to the Evaluacion.
        alumno_id: FK to the User (student).
        nota_final: Final grade as text (nullable — set when graded).
        registrada_at: Timestamp when the grade was registered (nullable).
    """

    __tablename__ = "resultado_evaluacion"
    __table_args__ = (
        Index("ix_resultado_evaluacion", "evaluacion_id"),
        Index("ix_resultado_alumno", "alumno_id"),
    )

    evaluacion_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("evaluacion.id", ondelete="CASCADE"),
        nullable=False,
    )
    alumno_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    nota_final: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None,
    )
    registrada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    alumno: Mapped[User] = relationship(
        "User",
        foreign_keys=[alumno_id],
        lazy="selectin",
    )
