"""Audit service — helper functions for creating audit log entries.

Centralizes audit log creation so that every module can record
significant actions with minimal boilerplate.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.audit_log_repository import AuditLogRepository


async def log_action(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    accion: str,
    *,
    detalle: dict | None = None,
    filas_afectadas: int = 1,
    materia_id: uuid.UUID | None = None,
    impersonado_id: uuid.UUID | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Create an audit log entry.

    Args:
        db: Database session.
        tenant_id: Tenant scope.
        actor_id: User who performed the action.
        accion: Standardized action code (e.g. "CALIFICACIONES_IMPORTAR").
        detalle: Optional JSON context.
        filas_afectadas: Number of records affected (default 1).
        materia_id: Optional related materia UUID.
        impersonado_id: Optional impersonated user UUID.
        ip: Client IP. If omitted and request is provided, extracted from request.
        user_agent: Client user-agent. If omitted and request is provided,
            extracted from request.
        request: FastAPI Request object (used to extract ip/user_agent if not
            provided explicitly).

    Returns:
        The created AuditLog instance.
    """
    # Extract IP and user_agent from request if not provided explicitly
    if ip is None and request is not None:
        ip = request.client.host if request.client else None
    if user_agent is None and request is not None:
        user_agent = request.headers.get("user-agent")

    repo = AuditLogRepository(session=db, tenant_id=tenant_id)
    record = await repo.create(
        actor_id=actor_id,
        accion=accion,
        detalle=detalle,
        filas_afectadas=filas_afectadas,
        materia_id=materia_id,
        impersonado_id=impersonado_id,
        ip=ip,
        user_agent=user_agent,
    )
    return record
