"""Padron models — VersionPadron and EntradaPadron.

Each import creates a new VersionPadron with activa=true and deactivates
the previous version. EntradaPadron rows hold student data with encrypted
email for PII protection.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.user import User


class VersionPadron(Base, TenantScopedMixin, SoftDeleteMixin):
    """A version of the student roster for a given materia x cohorte.

    Each import (manual or via Moodle WS) creates a new version. The
    previous active version is deactivated (activa=false) but preserved.

    Attributes:
        materia_id: FK to the subject.
        cohorte_id: FK to the cohort.
        cargado_por: FK to the user who imported this version.
        cargado_at: Timestamp when the import completed.
        activa: Whether this is the currently active version.
        modo: Import mode — 'moodle_ws' or 'archivo'.
    """

    __tablename__ = "version_padron"
    __table_args__ = (
        Index("ix_version_padron_materia_cohorte_activa",
              "materia_id", "cohorte_id", "activa"),
    )

    materia_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("materia.id", ondelete="CASCADE"),
        nullable=False,
    )
    cohorte_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("cohorte.id", ondelete="CASCADE"),
        nullable=False,
    )
    cargado_por: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    cargado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    activa: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    modo: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    entradas: Mapped[list[EntradaPadron]] = relationship(
        "EntradaPadron",
        back_populates="version",
        lazy="selectin",
    )
    cargador: Mapped[User] = relationship(
        "User",
        foreign_keys=[cargado_por],
        lazy="selectin",
    )


class EntradaPadron(Base, TenantScopedMixin, SoftDeleteMixin):
    """An individual student entry within a padron version.

    Each row represents one student in the roster. The email is stored
    encrypted (AES-256-GCM) and hashed (SHA-256) for PII protection.

    Attributes:
        version_id: FK to the parent VersionPadron.
        usuario_id: FK to User if matched by email_hash (nullable).
        nombre: First name (not encrypted).
        apellidos: Last name (not encrypted).
        email_cifrado: AES-256-GCM encrypted email (base64 text).
        email_hash: SHA-256 hash of email for matching.
        comision: Commission/group code (optional).
        regional: Regional office / delegation (optional).
    """

    __tablename__ = "entrada_padron"
    __table_args__ = (
        Index("ix_entrada_padron_version_id", "version_id"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("version_padron.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    nombre: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    apellidos: Mapped[str] = mapped_column(
        String(255), nullable=False,
    )
    email_cifrado: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
    )
    email_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    comision: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None,
    )
    regional: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None,
    )

    # ── ORM relationships ───────────────────────────────────────────────
    version: Mapped[VersionPadron] = relationship(
        "VersionPadron",
        back_populates="entradas",
    )
    usuario: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[usuario_id],
        lazy="selectin",
    )


