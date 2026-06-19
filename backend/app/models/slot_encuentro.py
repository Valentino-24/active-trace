"""SlotEncuentro model — a template for recurring synchronous class sessions.

Supports two mutually exclusive modes per RN-13:
    - Recurrente: cant_semanas > 0, fecha_unica = NULL
    - Fecha única: cant_semanas = 0, fecha_unica = NOT NULL

Each slot generates N InstanciaEncuentro records at creation time.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class SlotEncuentro(Base, TenantScopedMixin, SoftDeleteMixin):
    """Template for a recurring class session (slot).

    Attributes:
        asignacion_id: FK to the teacher's Asignacion.
        materia_id: FK to Materia.
        titulo: Display title (e.g. "Clase de Programación I").
        hora: Time string (e.g. "18:00").
        dia_semana: Day of week (e.g. "Lunes").
        fecha_inicio: Start date for instance generation.
        cant_semanas: Number of weeks (0 = single date mode).
        fecha_unica: Specific date for single-instance mode (nullable).
        meet_url: Optional meeting URL.
        vig_desde: Start of validity period.
        vig_hasta: End of validity period (nullable).
    """

    __tablename__ = "slot_encuentro"

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
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    hora: Mapped[str] = mapped_column(String(10), nullable=False)
    dia_semana: Mapped[str] = mapped_column(String(15), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    cant_semanas: Mapped[int] = mapped_column(nullable=False, default=0)
    fecha_unica: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    meet_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, default=None)
    vig_desde: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    vig_hasta: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
