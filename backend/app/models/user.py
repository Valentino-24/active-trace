"""User model — identity, authentication, and extended PII data.

Each user belongs to a tenant (via TenantScopedMixin).
Email is unique within a tenant via composite unique constraint.
PII fields (email, dni, cuil, cbu, alias_cbu) are encrypted at rest
with AES-256-GCM. The email_hash column enables fast lookups without
decrypting the email field.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin

if TYPE_CHECKING:
    from app.models.asignacion import Asignacion


class User(Base, TenantScopedMixin, SoftDeleteMixin):
    """A user account within a tenant.

    Attributes:
        email: Email address (AES-256-GCM encrypted, unique per tenant).
        email_hash: SHA-256 hash of email for deterministic lookup.
        password_hash: Argon2id password hash.
        totp_secret: Encrypted TOTP secret (AES-256), nullable.
        totp_enabled: Whether 2FA is active.
        display_name: Human-readable display name.
        nombre: First name (not encrypted).
        apellidos: Last name (not encrypted).
        dni: National ID document (AES-256-GCM encrypted).
        cuil: Tax ID (AES-256-GCM encrypted).
        cbu: Bank account number (AES-256-GCM encrypted).
        alias_cbu: Bank alias (AES-256-GCM encrypted).
        banco: Bank name (not encrypted).
        regional: Regional office / delegation.
        legajo: Institutional file number (business attribute, not PK).
        legajo_profesional: Professional registry number.
        facturador: Whether user issues invoices.
        estado: Account status — activo | inactivo.
        is_active: Whether the account is active (soft disable).
        roles: List of UserRole assignments (one-to-many).
        permissions: Set of effective permission codes (loaded by get_current_user).
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    # ── Auth fields ────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Extended PII fields ────────────────────────────────────────────
    nombre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    apellidos: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dni: Mapped[str | None] = mapped_column(Text, nullable=True)       # AES-256-GCM
    cuil: Mapped[str | None] = mapped_column(Text, nullable=True)      # AES-256-GCM
    cbu: Mapped[str | None] = mapped_column(Text, nullable=True)       # AES-256-GCM
    alias_cbu: Mapped[str | None] = mapped_column(Text, nullable=True) # AES-256-GCM
    banco: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regional: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legajo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legajo_profesional: Mapped[str | None] = mapped_column(String(100), nullable=True)
    facturador: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")

    # ── Auto-compute email_hash when email is set ───────────────────────

    @validates("email")
    def _validate_email(self, key: str, value: str) -> str:
        """Auto-compute email_hash whenever email is set."""
        if value is not None:
            self.email_hash = self.compute_email_hash(value)
        return value

    # ── ORM relationships ───────────────────────────────────────────────
    roles: Mapped[list] = relationship(
        "UserRole", lazy="selectin"
    )

    asignaciones: Mapped[list[Asignacion]] = relationship(
        "Asignacion",
        foreign_keys="Asignacion.usuario_id",
        lazy="selectin",
    )

    asignaciones_responsable: Mapped[list[Asignacion]] = relationship(
        "Asignacion",
        foreign_keys="Asignacion.responsable_id",
        lazy="selectin",
    )

    # ── Non-persistent attributes (set by get_current_user) ─────────────
    _permissions = None
    _impersonator_user = None

    # ── Computed properties ─────────────────────────────────────────────

    @property
    def permissions(self) -> set[str]:
        """Effective permission codes (modulo:accion) for this user.

        Returns an empty set if permissions have not been loaded yet.
        Permissions are loaded by get_current_user after authentication.
        """
        if self._permissions is None:
            return set()
        return self._permissions

    @permissions.setter
    def permissions(self, value: set[str]) -> None:
        self._permissions = value

    @property
    def is_impersonating(self) -> bool:
        """True when this user is under an impersonation session."""
        return self._impersonator_user is not None

    # ── Email hash helper ────────────────────────────────────────────────

    @staticmethod
    def compute_email_hash(email: str) -> str:
        """Compute deterministic email hash for lookup.

        Uses SHA-256 on the lowercased, stripped email.
        This is NOT a security mechanism — it enables fast lookups
        without requiring decryption of every row.
        """
        return hashlib.sha256(
            email.lower().strip().encode("utf-8")
        ).hexdigest()
