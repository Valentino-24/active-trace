"""RBAC models — Role, Permission, RolePermission, UserRole.

Defines the authorization model for activia-trace:
- Role and Permission are tenant-scoped catalogs.
- RolePermission is a pure N:N relationship (no tenant scope, no soft delete).
- UserRole assigns a role to a user with optional validity dates.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModelMixin, SoftDeleteMixin, TenantScopedMixin


class Role(Base, TenantScopedMixin, SoftDeleteMixin):
    """A role within a tenant (e.g. PROFESOR, ADMIN).

    Attributes:
        nombre: Human-readable name (e.g. "Profesor").
        codigo: Unique code per tenant (e.g. "PROFESOR").
        descripcion: Optional description of the role.
    """

    __tablename__ = "role"
    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_role_tenant_codigo"),
    )

    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)


class Permission(Base, TenantScopedMixin, SoftDeleteMixin):
    """A fine-grained permission within a tenant.

    Permissions use the format ``modulo:accion`` (e.g. ``calificaciones:importar``).

    Attributes:
        codigo: Permission code in ``modulo:accion`` format (unique per tenant).
        descripcion: Optional description.
    """

    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_permission_tenant_codigo"),
    )

    codigo: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None)


class RolePermission(Base, BaseModelMixin):
    """N:N relationship between roles and permissions.

    This is a pure relationship table — NO tenant scope, NO soft delete.
    It only exists to associate which permissions each role grants.
    """

    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permission"
        ),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("permission.id", ondelete="CASCADE"),
        nullable=False,
    )


class UserRole(Base, TenantScopedMixin, SoftDeleteMixin):
    """Assignment of a role to a user with validity dates.

    Attributes:
        user_id: FK to the user receiving the role.
        role_id: FK to the assigned role.
        desde: Date from which the role is valid.
        hasta: Optional date after which the role is no longer valid.
    """

    __tablename__ = "user_role"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "role_id", "desde", name="uq_user_role_desde"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False,
    )
    desde: Mapped[date] = mapped_column(Date, nullable=False)
    hasta: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)

    # ORM relationships for navigation
    role: Mapped[Role] = relationship(Role, lazy="joined")
