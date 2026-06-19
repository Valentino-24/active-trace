"""Tareas router — API endpoints for internal task management.

Endpoints (guard: tareas:gestionar):
    POST   /api/tareas                  — create a task
    GET    /api/tareas/mias             — list own tasks
    GET    /api/tareas                  — admin list all tasks
    PATCH  /api/tareas/{id}/estado      — change task state
    PATCH  /api/tareas/{id}/asignar     — reassign task
    POST   /api/tareas/{id}/comentarios — add comment
    GET    /api/tareas/{id}/comentarios — list comments
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.tareas import (
    ComentarioCrearRequest,
    ComentarioListResponse,
    ComentarioResponse,
    TareaCrearRequest,
    TareaEstadoUpdateRequest,
    TareaListResponse,
    TareaReasignarRequest,
    TareaResponse,
)
from app.services.tarea_service import TareaService

router = APIRouter(tags=["tareas"])


@router.post(
    "/api/tareas",
    response_model=TareaResponse,
    status_code=201,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def crear_tarea(
    body: TareaCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task assigned to a team member."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.crear(body)


@router.get(
    "/api/tareas/mias",
    response_model=TareaListResponse,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def mis_tareas(
    estado: str | None = Query(default=None),
    materia_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks assigned to the authenticated user."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_mias(estado=estado, materia_id=materia_id)


@router.get(
    "/api/tareas",
    response_model=TareaListResponse,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def listar_tareas(
    asignado_a: uuid.UUID | None = Query(default=None),
    asignado_por: uuid.UUID | None = Query(default=None),
    materia_id: uuid.UUID | None = Query(default=None),
    estado: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin list — all tasks in the tenant with filters."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_admin(
        asignado_a=asignado_a, asignado_por=asignado_por,
        materia_id=materia_id, estado=estado, q=q,
    )


@router.patch(
    "/api/tareas/{tarea_id}/estado",
    response_model=TareaResponse,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def cambiar_estado(
    tarea_id: uuid.UUID,
    body: TareaEstadoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change a task's state (with transition validation)."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.cambiar_estado(tarea_id, body)


@router.patch(
    "/api/tareas/{tarea_id}/asignar",
    response_model=TareaResponse,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def reasignar_tarea(
    tarea_id: uuid.UUID,
    body: TareaReasignarRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reassign a task to a different user."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.reasignar(tarea_id, body)


@router.post(
    "/api/tareas/{tarea_id}/comentarios",
    response_model=ComentarioResponse,
    status_code=201,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def agregar_comentario(
    tarea_id: uuid.UUID,
    body: ComentarioCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a task thread."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.agregar_comentario(tarea_id, body)


@router.get(
    "/api/tareas/{tarea_id}/comentarios",
    response_model=ComentarioListResponse,
    dependencies=[Depends(require_permission("tareas:gestionar"))],
)
async def listar_comentarios(
    tarea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all comments for a task (ASC chronological order)."""
    service = TareaService(
        db=db, tenant_id=current_user.tenant_id, current_user=current_user,
    )
    return await service.listar_comentarios(tarea_id)
