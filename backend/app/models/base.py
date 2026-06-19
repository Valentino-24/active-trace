"""Base ORM mixins for all domain entities.

Provides three mixin levels:
    - BaseModelMixin: UUID pk + timestamps (for Tenant itself).
    - TenantScopedMixin(BaseModelMixin): adds tenant_id FK (for domain entities).
    - SoftDeleteMixin: deleted_at for soft delete support.

Tenant inherits BaseModelMixin.
All other domain entities inherit TenantScopedMixin + SoftDeleteMixin + Base.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column


class BaseModelMixin:
    """Core mixin: UUID pk + created_at / updated_at timestamps.

    Used by Tenant (root entity) directly.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class TenantScopedMixin(BaseModelMixin):
    """Extends BaseModelMixin with a tenant_id FK.

    All domain entities (except Tenant itself) inherit from this mixin
    to enforce multi-tenant row-level isolation.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(as_uuid=True),
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin that adds soft delete support via deleted_at field.

    When an entity is soft-deleted, deleted_at is set to the current timestamp.
    The record is NOT physically removed from the database.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
