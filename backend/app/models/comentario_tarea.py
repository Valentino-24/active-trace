"""ComentarioTarea model — comment thread for internal tasks.

Each record is an immutable audit trail entry — no edits, no deletes.
Part of Epica 8 (F8.1–F8.3).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModelMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.tarea import Tarea


class ComentarioTarea(Base, TenantScopedMixin):
    """An immutable comment on a task — audit trail, NO soft delete.

    Attributes:
        tarea_id: FK to the parent Tarea.
        autor_id: FK to User who wrote the comment.
        texto: Comment body text.
        creado_at: When the comment was created (client-provided or server-default).
    """

    __tablename__ = "comentario_tarea"
    __table_args__ = (
        Index("ix_comentario_tarea", "tarea_id"),
    )

    tarea_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("tarea.id", ondelete="CASCADE"),
        nullable=False,
    )
    autor_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    texto: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    tarea: Mapped["Tarea"] = relationship(
        "Tarea",
        back_populates="comentarios",
    )
