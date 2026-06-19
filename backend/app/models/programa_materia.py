"""ProgramaMateria model — official syllabus document for a materia.

Each ProgramaMateria associates a document (referencia_archivo) to a
specific materia × carrera × cohorte combination.
Part of F5.3 — Gestion de programas de materias.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class ProgramaMateria(Base, TenantScopedMixin, SoftDeleteMixin):
    """A syllabus/program document for a materia in a carrera × cohorte.

    Attributes:
        materia_id: FK to Materia.
        carrera_id: FK to Carrera.
        cohorte_id: FK to Cohorte.
        titulo: Descriptive title.
        referencia_archivo: Opaque reference to the stored document.
    """

    __tablename__ = "programa_materia"
    __table_args__ = (
        Index("ix_programa_materia_cohorte", "materia_id", "cohorte_id"),
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
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    referencia_archivo: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None,
    )
    cargado_at: Mapped["DateTime | None"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
