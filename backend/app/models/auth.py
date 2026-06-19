"""Auth-related models: RefreshToken and PasswordResetToken.

These are session/reset-tracking entities that reference User
and are NOT tenant-scoped — they belong to the User directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseModelMixin


class RefreshToken(Base, BaseModelMixin):
    """An opaque refresh token for session management.

    The actual token is 64 random bytes (hex) stored as SHA256 hash.
    Allows revocation and reuse detection.

    Attributes:
        user_id: FK to User.
        token_hash: SHA256 hash of the opaque token.
        expires_at: When this token expires.
        revoked_at: When this token was revoked (null if active).
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class PasswordResetToken(Base, BaseModelMixin):
    """A single-use password reset token.

    Attributes:
        user_id: FK to User.
        token_hash: SHA256 hash of the opaque token.
        expires_at: When this token expires (30 min from creation).
        used_at: When this token was used (null if unused).
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
