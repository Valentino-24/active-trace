"""InstanciaEncuentro model — a concrete class session derived from a slot.

Each instance has its own state (Programado|Realizado|Cancelado) that can be
modified independently without affecting the slot or other instances (RN-14).

Instances can be created standalone (slot_id=NULL) for ad-hoc sessions.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class EstadoInstancia(str, enum.Enum):
    """State of a concrete class session (RN-14).

    Any state → any state — fully independent transitions.
    """

    Programado = "Programado"
    Realizado = "Realizado"
    Cancelado = "Cancelado"


class InstanciaEncuentro(Base, TenantScopedMixin, SoftDeleteMixin):
    """A concrete class session instance.

    Attributes:
        slot_id: FK to SlotEncuentro (nullable for ad-hoc instances).
        materia_id: FK to Materia.
        fecha: Date of the session.
        hora: Time of the session.
        titulo: Instance title (auto-generated from slot titulo + #N).
        estado: Current state (Programado|Realizado|Cancelado).
        meet_url: Optional meeting URL (can differ from slot).
        video_url: Optional recording URL.
        comentario: Optional teacher's notes.
    """

    __tablename__ = "instancia_encuentro"

    slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("slot_encuentro.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    materia_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora: Mapped[str] = mapped_column(String(10), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoInstancia.Programado.value,
    )
    meet_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None,
    )
    video_url: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, default=None,
    )
    comentario: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
    )
