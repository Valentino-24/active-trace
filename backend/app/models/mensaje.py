"""Mensaje model — internal messaging between users."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Mensaje(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "mensaje"

    remitente_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    destinatario_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    asunto: Mapped[str] = mapped_column(String(255), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leido_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
