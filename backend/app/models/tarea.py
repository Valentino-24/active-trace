"""Tarea model — internal task management for teaching staff.

Each Tarea represents a unit of work assigned to a docent, with
state transitions (Pendiente → EnProgreso → Resuelta / Cancelada),
delegation tracing, and an optional comment thread.
Part of Epica 8 (F8.1–F8.3).
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.materia import Materia
    from app.models.comentario_tarea import ComentarioTarea


class EstadoTarea(str, enum.Enum):
    """Workflow states for a Tarea.

    Pendiente: Newly created, not yet started.
    EnProgreso: Work in progress.
    Resuelta: Completed — terminal state.
    Cancelada: Cancelled — terminal state.
    """

    Pendiente = "Pendiente"
    EnProgreso = "EnProgreso"
    Resuelta = "Resuelta"
    Cancelada = "Cancelada"


class Tarea(Base, TenantScopedMixin, SoftDeleteMixin):
    """An internal task assigned to a teaching staff member.

    Attributes:
        materia_id: Optional FK to Materia (nullable — standalone tasks allowed).
        asignado_a: FK to User who is responsible for the task.
        asignado_por: FK to User who created/assigned the task.
        estado: Current workflow state (Pendiente|EnProgreso|Resuelta|Cancelada).
        descripcion: Text description of the task.
        contexto_id: Optional external context reference (free UUID).
    """

    __tablename__ = "tarea"
    __table_args__ = (
        Index("ix_tarea_asignado", "tenant_id", "asignado_a", "deleted_at"),
        Index("ix_tarea_estado", "tenant_id", "estado"),
    )

    materia_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    asignado_a: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    asignado_por: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EstadoTarea.Pendiente.value,
    )
    descripcion: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    contexto_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        nullable=True,
        default=None,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    materia: Mapped["Materia | None"] = relationship(
        "Materia",
        lazy="selectin",
    )
    comentarios: Mapped[list["ComentarioTarea"]] = relationship(
        "ComentarioTarea",
        back_populates="tarea",
        lazy="selectin",
        order_by="ComentarioTarea.creado_at.asc()",
    )
