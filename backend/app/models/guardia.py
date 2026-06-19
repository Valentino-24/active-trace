"""Guardia model — an independent tutor duty / office hours record.

Guardias are NOT linked to Encuentros. They represent blocks of time where
a TUTOR or PROFESOR is available for student consultations.

Each guardia is independently created with its own state.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class EstadoGuardia(str, enum.Enum):
    """State of a guardia record."""

    Pendiente = "Pendiente"
    Realizada = "Realizada"
    Cancelada = "Cancelada"


class Guardia(Base, TenantScopedMixin, SoftDeleteMixin):
    """A tutor duty / office hours record.

    Attributes:
        asignacion_id: FK to the tutor's Asignacion.
        materia_id: FK to Materia.
        carrera_id: FK to Carrera.
        cohorte_id: FK to Cohorte.
        dia: Day of the week (e.g. "Lunes").
        horario: Time range (e.g. "14:00-14:45").
        estado: Current state (Pendiente|Realizada|Cancelada).
        comentarios: Optional notes.
        creada_at: When the record was created.
    """

    __tablename__ = "guardia"

    asignacion_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("asignacion.id", ondelete="CASCADE"),
        nullable=False,
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
    dia: Mapped[str] = mapped_column(String(15), nullable=False)
    horario: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoGuardia.Pendiente.value,
    )
    comentarios: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
    )
    creada_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
