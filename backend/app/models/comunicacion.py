"""Comunicacion model — outbound communication with state machine.

Each Comunicacion represents a message sent to one recipient, grouped
by lote_id for batch operations. The state machine follows RN-15:
Pendiente → Enviando → Enviado | Error | Cancelado.

Recipient emails are encrypted at rest (AES-256-GCM) and never exposed
in API responses or logs.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.materia import Materia
    from app.models.user import User


class EstadoComunicacion(str, enum.Enum):
    """State machine for communication lifecycle (RN-15).

    Valid transitions:
        Pendiente → Enviando → Enviado | Error
        Pendiente → Cancelado
        Enviando  → Enviado | Error
    Terminal states: Enviado, Error, Cancelado
    """

    Pendiente = "Pendiente"
    Enviando = "Enviando"
    Enviado = "Enviado"
    Error = "Error"
    Cancelado = "Cancelado"


class Comunicacion(Base, TenantScopedMixin, SoftDeleteMixin):
    """An outbound communication message to a single recipient.

    Attributes:
        enviado_por: FK to the User who created/queued the message.
        aprobado_por: FK to the User who approved the message (nullable).
        materia_id: FK to Materia (context for the communication).
        destinatario: AES-256-GCM encrypted recipient email.
        asunto: Rendered subject line.
        cuerpo: Rendered message body.
        estado: Current state in the state machine.
        lote_id: UUID grouping messages sent in the same batch (nullable).
        fecha_aprobacion: When the message was approved (nullable).
        enviado_at: When the message was sent by the worker (nullable).
    """

    __tablename__ = "comunicacion"
    __table_args__ = (
        Index("ix_comunicacion_lote", "lote_id"),
        Index("ix_comunicacion_estado", "tenant_id", "estado"),
        Index("ix_comunicacion_materia", "tenant_id", "materia_id"),
    )

    enviado_por: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    aprobado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    materia_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    destinatario: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    asunto: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    cuerpo: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoComunicacion.Pendiente.value,
    )
    lote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True), nullable=True, default=None, index=True,
    )
    fecha_aprobacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )
    enviado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    remitente: Mapped[User] = relationship(
        "User",
        foreign_keys=[enviado_por],
        lazy="selectin",
    )
    aprobador: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[aprobado_por],
        lazy="selectin",
    )
    materia: Mapped[Materia] = relationship(
        "Materia",
        lazy="selectin",
    )
