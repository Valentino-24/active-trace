"""Materia model — a subject/course within a tenant's catalogue.

Materia is the academic catalogue entity: a subject that can be taught
across multiple carreras and cohorts. It is distinct from Dictado,
which represents the actual teaching instance of a materia in a
specific carrera × cohorte combination.
"""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin


class Materia(Base, TenantScopedMixin, SoftDeleteMixin):
    """A subject/course within a tenant's academic catalogue.

    Attributes:
        codigo: Short unique code per tenant (e.g. 'PROG1').
        nombre: Full subject name (e.g. 'Programación I').
        estado: 'activa' | 'inactiva'
    """

    __tablename__ = "materia"
    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_materia_tenant_codigo"),
    )

    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="activa"
    )
    grupo_plus: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None,
    )
