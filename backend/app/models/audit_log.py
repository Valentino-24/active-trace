"""AuditLog model — immutable append-only audit trail.

All significant actions in the system are recorded here.
This model does NOT inherit SoftDeleteMixin — records are
append-only and cannot be modified or deleted.

Fields defined by E-AUD in the knowledge base.
"""

from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TenantScopedMixin


class AuditLog(Base, TenantScopedMixin):
    """Immutable audit log entry.

    All significant actions in the system are recorded here.
    This model does NOT inherit SoftDeleteMixin — records are
    append-only and cannot be modified or deleted.

    Fields defined by E-AUD in the knowledge base.
    """

    __table_args__ = (
        Index("ix_audit_log_tenant_accion", "tenant_id", "accion"),
        Index("ix_audit_log_tenant_fecha", "tenant_id", "fecha_hora"),
    )

    __tablename__ = "audit_log"

    # ── Timestamp of the action (separate from created_at) ──────────
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Actor info ──────────────────────────────────────────────────
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=False,
        index=True,
    )
    impersonado_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        default=None,
    )

    # ── Domain context ──────────────────────────────────────────────
    # materia_id FK will be added in C-06 when the materia table exists.
    materia_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        default=None,
    )

    # ── Action info ─────────────────────────────────────────────────
    accion: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    detalle: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    filas_afectadas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # ── Request context ─────────────────────────────────────────────
    ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        default=None,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        default=None,
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} accion='{self.accion}' "
            f"actor_id={self.actor_id} filas={self.filas_afectadas}>"
        )
