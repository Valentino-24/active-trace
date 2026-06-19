"""Tenant model — root entity for multi-tenancy.

Each tenant represents an institution (a customer).
Every domain record belongs to a tenant via tenant_id FK.
"""

from __future__ import annotations

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseModelMixin, SoftDeleteMixin


class Tenant(Base, BaseModelMixin, SoftDeleteMixin):
    """An institution (customer) in the multi-tenant system.

    Uses BaseModelMixin (NOT TenantScopedMixin) because Tenant is the
    root entity — it does NOT reference itself via tenant_id.

    Attributes:
        nombre: Human-readable institution name.
        codigo: Short unique code per system (e.g. 'utn-frc').
        configuracion: JSONB for tenant-specific config (branding, scales, etc.).
        estado: 'activo' | 'inactivo'
    """

    __tablename__ = "tenant"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_tenant_codigo"),
    )

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    configuracion: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="activo", server_default="activo"
    )
