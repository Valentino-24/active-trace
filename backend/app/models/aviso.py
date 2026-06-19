"""Aviso model — institutional notice board.

Each Aviso represents an institutional announcement that can be
segmented by audience (alcance), has a validity window, and optional
read acknowledgment. Part of F3.5 — Tablón de avisos.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.materia import Materia
    from app.models.cohorte import Cohorte


class AlcanceAviso(str, enum.Enum):
    """Audience scope for an aviso (RN-20).

    Global: Visible to all users in the tenant.
    PorMateria: Visible only to users assigned to the specific materia.
    PorCohorte: Visible only to users belonging to the cohorte.
    PorRol: Visible only to users with the specific role.
    """

    Global = "Global"
    PorMateria = "PorMateria"
    PorCohorte = "PorCohorte"
    PorRol = "PorRol"


class SeveridadAviso(str, enum.Enum):
    """Severity level for an aviso.

    Info: Informational notice.
    Advertencia: Warning — requires attention.
    Crítico: Critical — urgent action needed.
    """

    Info = "Info"
    Advertencia = "Advertencia"
    Crítico = "Crítico"


class Aviso(Base, TenantScopedMixin, SoftDeleteMixin):
    """An institutional notice/announcement.

    Attributes:
        alcance: Audience scope (Global|PorMateria|PorCohorte|PorRol).
        materia_id: FK to Materia (nullable, for PorMateria scope).
        cohorte_id: FK to Cohorte (nullable, for PorCohorte scope).
        rol_destino: Target role code (nullable, for PorRol scope).
        severidad: Severity level (Info|Advertencia|Crítico).
        titulo: Notice title.
        cuerpo: Notice body text.
        inicio_en: Validity window start.
        fin_en: Validity window end.
        orden: Display order (lower = higher priority).
        activo: Whether the notice is currently published.
        requiere_ack: Whether read acknowledgment is required.
    """

    __tablename__ = "aviso"
    __table_args__ = (
        Index("ix_aviso_activo_vigencia", "tenant_id", "activo", "inicio_en", "fin_en"),
        Index("ix_aviso_alcance", "tenant_id", "alcance"),
    )

    alcance: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    materia_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )
    cohorte_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("cohorte.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )
    rol_destino: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None,
    )
    severidad: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    titulo: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    cuerpo: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    inicio_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    fin_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    orden: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    requiere_ack: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    materia: Mapped["Materia | None"] = relationship(
        "Materia",
        lazy="selectin",
    )
    cohorte: Mapped["Cohorte | None"] = relationship(
        "Cohorte",
        lazy="selectin",
    )
