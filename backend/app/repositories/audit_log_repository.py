"""AuditLog repository — append-only data access.

Only exposes create() and list().
No update, delete, or soft-delete — AuditLog is immutable.
"""

from __future__ import annotations

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """Append-only repository for AuditLog.

    Only create and list are exposed; update, soft_delete are
    blocked at the application level. The Alembic migration also
    adds REVOKE UPDATE, DELETE at the database level.
    """

    _model_cls = AuditLog

    async def update(self, id: object = None, **kwargs: object):  # type: ignore[override]
        """Not supported — AuditLog is append-only."""
        raise RuntimeError("AuditLog does not support update")

    async def soft_delete(self, id: object = None):  # type: ignore[override]
        """Not supported — AuditLog is append-only."""
        raise RuntimeError("AuditLog does not support delete")
