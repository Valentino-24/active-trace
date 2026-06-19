"""User model — identity and authentication.

Each user belongs to a tenant (via TenantScopedMixin).
Email is unique within a tenant via composite unique constraint.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class User(Base, TenantScopedMixin, SoftDeleteMixin):
    """A user account within a tenant.

    Attributes:
        email: Email address (unique per tenant).
        password_hash: Argon2id password hash.
        totp_secret: Encrypted TOTP secret (AES-256), nullable.
        totp_enabled: Whether 2FA is active.
        display_name: Human-readable display name.
        is_active: Whether the account is active (soft disable).
        roles: List of UserRole assignments (one-to-many).
        permissions: Set of effective permission codes (loaded by get_current_user).
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── ORM relationships ───────────────────────────────────────────────
    roles: Mapped[list[UserRole]] = relationship(
        "UserRole", lazy="selectin"
    )

    # ── Non-persistent attributes (set by get_current_user) ─────────────
    # _permissions: set by get_current_user to cache permissions per request.
    # _impersonator_user: set when this user is under impersonation.
    # (no type annotations — SQLAlchemy would try to map them as columns)
    _permissions = None
    _impersonator_user = None

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
        """True when this user is under an impersonation session.

        When impersonation is active, the User object represents the
        impersonated user (effective identity), and _impersonator_user
        holds the real actor performing the impersonation.
        """
        return self._impersonator_user is not None
