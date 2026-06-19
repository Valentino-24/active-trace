"""Carrera model — a degree programme or career path within a tenant.

Each tenant can define multiple carreras (e.g. "Técnico Universitario en
Programación", "Licenciatura en Administración"). Carrera is the root entity
for the academic structure: cohorts belong to a carrera, and dictados
reference a carrera.
"""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Carrera(Base, TenantScopedMixin, SoftDeleteMixin):
    """A degree programme or career path within a tenant.

    Attributes:
        codigo: Short unique code per tenant (e.g. 'TUP').
        nombre: Full name (e.g. 'Técnico Universitario en Programación').
        estado: 'activa' | 'inactiva'
    """

    __tablename__ = "carrera"
    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_carrera_tenant_codigo"),
    )

    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="activa"
    )
