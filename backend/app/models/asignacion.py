"""Asignacion model — links a user to a role within an academic context.

An asignacion answers: "Who has which role, in what subject/career/cohort,
for which period, and who supervises them?"

The estado_vigencia is derived from dates, not stored in the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Asignacion(Base, TenantScopedMixin, SoftDeleteMixin):
    """Links a user to a role within an academic context with validity.

    Attributes:
        usuario_id: FK to the assigned user.
        rol: Role code (PROFESOR, TUTOR, COORDINADOR, NEXO, ADMIN, FINANZAS).
        materia_id: FK to Materia (nullable for global roles).
        carrera_id: FK to Carrera (nullable).
        cohorte_id: FK to Cohorte (nullable).
        comisiones: List of commission codes assigned (JSON array).
        responsable_id: FK to the supervising user (nullable).
        desde: Start date of the assignment validity.
        hasta: End date (nullable = open-ended).
    """

    __tablename__ = "asignacion"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    materia_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    carrera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("carrera.id", ondelete="SET NULL"),
        nullable=True,
    )
    cohorte_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("cohorte.id", ondelete="SET NULL"),
        nullable=True,
    )
    comisiones: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    desde: Mapped[date] = mapped_column(Date, nullable=False)
    hasta: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── ORM relationships ───────────────────────────────────────────────
    usuario: Mapped["User"] = relationship(
        "User",
        foreign_keys=[usuario_id],
        lazy="selectin",
    )
    responsable: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[responsable_id],
        lazy="selectin",
    )

    # ── Computed properties ─────────────────────────────────────────────

    @property
    def estado_vigencia(self) -> str:
        """Derive the validity status from dates.

        Returns one of:
            - "pendiente": desde is in the future
            - "vigente": desde <= today and (hasta IS NULL or hasta >= today)
            - "vencida": hasta < today
        """
        today = datetime.now(UTC).date()
        if self.desde > today:
            return "pendiente"
        if self.hasta is not None and self.hasta <= today:
            return "vencida"
        return "vigente"

    @property
    def vigente(self) -> bool:
        """Convenience: is this assignment currently valid?"""
        return self.estado_vigencia == "vigente"

    # ── To avoid circular import at runtime ─────────────────────────────
    # The forward-reference to "User" is resolved at model metadata time
    # by SQLAlchemy. The TYPE_CHECKING guard in user.py handles the reverse.
