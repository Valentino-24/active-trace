"""AcknowledgmentAviso model — read acknowledgment for notices.

Each record represents a user confirming they have read a specific
notice. This is an immutable audit record — NO soft delete.

Part of F3.5 — Tablón de avisos con acuse de recibo.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseModelMixin, TenantScopedMixin


class AcknowledgmentAviso(Base, TenantScopedMixin):
    """Immutable record of a user confirming they read a notice.

    This model does NOT inherit SoftDeleteMixin — acknowledgments
    are audit records and cannot be modified or deleted.

    Attributes:
        aviso_id: FK to the aviso being acknowledged.
        usuario_id: FK to the user who acknowledged.
        confirmado_at: When the acknowledgment occurred.
    """

    __tablename__ = "acknowledgment_aviso"
    __table_args__ = (
        Index("ix_ack_aviso", "aviso_id"),
        Index("ix_ack_usuario", "usuario_id"),
        Index("ix_ack_aviso_usuario", "aviso_id", "usuario_id", unique=True),
    )

    aviso_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("aviso.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    confirmado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AcknowledgmentAviso aviso_id={self.aviso_id} "
            f"usuario_id={self.usuario_id} confirmado_at={self.confirmado_at}>"
        )
