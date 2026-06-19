"""ReservaEvaluacion model — student booking for an evaluation slot.

Each reservation links a student (alumno) to an Evaluacion with a
chosen date/time and tracks its lifecycle via estado.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.user import User


class EstadoReserva(str, enum.Enum):
    """State machine for reservation lifecycle.

    Activa: Reservation is active and counts toward cupo.
    Cancelada: Reservation was cancelled by the student.
    """

    Activa = "Activa"
    Cancelada = "Cancelada"


class ReservaEvaluacion(Base, TenantScopedMixin, SoftDeleteMixin):
    """A student's reservation for an evaluation slot.

    Attributes:
        evaluacion_id: FK to the Evaluacion.
        alumno_id: FK to the User (student).
        fecha_hora: Date and time of the reserved slot.
        estado: Current state — Activa or Cancelada.
    """

    __tablename__ = "reserva_evaluacion"
    __table_args__ = (
        Index("ix_reserva_evaluacion", "evaluacion_id"),
        Index("ix_reserva_alumno", "alumno_id"),
        Index("ix_reserva_activa", "tenant_id", "estado"),
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
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoReserva.Activa.value,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    alumno: Mapped[User] = relationship(
        "User",
        foreign_keys=[alumno_id],
        lazy="selectin",
    )
