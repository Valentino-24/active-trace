"""Tarea service — CRUD, state transitions, delegation, and comments.

Implements:
    - State machine with transition validation
    - Scope: mis_tareas (own) vs admin (all)
    - Delegation with audit trail
    - Comment thread (immutable)
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tarea import EstadoTarea, Tarea
from app.models.user import User
from app.repositories.tarea_repository import ComentarioTareaRepository, TareaRepository
from app.schemas.tareas import (
    ComentarioCrearRequest,
    ComentarioListResponse,
    ComentarioResponse,
    TareaCrearRequest,
    TareaEstadoUpdateRequest,
    TareaListResponse,
    TareaMiaResponse,
    TareaReasignarRequest,
    TareaResponse,
)
from app.services.audit_service import log_action

# ── State machine ────────────────────────────────────────────────────────────

_TRANSICIONES: dict[EstadoTarea, set[EstadoTarea]] = {
    EstadoTarea.Pendiente: {EstadoTarea.EnProgreso, EstadoTarea.Cancelada},
    EstadoTarea.EnProgreso: {EstadoTarea.Resuelta, EstadoTarea.Cancelada},
    EstadoTarea.Resuelta: set(),   # terminal
    EstadoTarea.Cancelada: set(),  # terminal
}


def _validar_transicion(actual: str, nueva: str) -> None:
    """Validate state transition. Raises HTTPException(409) if invalid."""
    actual_enum = EstadoTarea(actual)
    nueva_enum = EstadoTarea(nueva)
    permitidas = _TRANSICIONES.get(actual_enum, set())
    if nueva_enum not in permitidas:
        raise HTTPException(
            status_code=409,
            detail=f"Transición inválida: {actual} → {nueva}",
        )


class TareaService:
    """Service for internal task management."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._tarea_repo = TareaRepository(session=db, tenant_id=tenant_id)
        self._coment_repo = ComentarioTareaRepository(session=db, tenant_id=tenant_id)

    # ── Helpers ────────────────────────────────────────────────────────────

    async def _get_tarea_or_404(self, tarea_id: uuid.UUID) -> Tarea:
        """Fetch non-deleted tarea by id or raise 404."""
        tarea = await self._tarea_repo.get(tarea_id)
        if tarea is None:
            raise HTTPException(status_code=404, detail="Tarea no encontrada")
        return tarea

    def _is_admin(self) -> bool:
        """Check if current user has admin scope (COORDINADOR/ADMIN)."""
        roles = getattr(self._current_user, "roles", [])
        if not isinstance(roles, list):
            roles = [roles] if roles else []
        for ur in roles:
            role = getattr(ur, "role", None)
            if role is not None and role.codigo in ("COORDINADOR", "ADMIN"):
                return True
        return False

    # ── Crear ─────────────────────────────────────────────────────────────

    async def crear(self, data: TareaCrearRequest) -> TareaResponse:
        """Create a new task assigned to a user."""
        tarea = await self._tarea_repo.create(
            materia_id=data.materia_id,
            asignado_a=data.asignado_a,
            asignado_por=self._current_user.id,
            estado=EstadoTarea.Pendiente.value,
            descripcion=data.descripcion,
            contexto_id=data.contexto_id,
        )
        await self._db.flush()

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="TAREA_CREAR",
            detalle={
                "tarea_id": str(tarea.id),
                "asignado_a": str(tarea.asignado_a),
            },
        )
        return self._to_response(tarea)

    # ── Mis tareas ────────────────────────────────────────────────────────

    async def listar_mias(
        self,
        estado: str | None = None,
        materia_id: uuid.UUID | None = None,
    ) -> TareaListResponse:
        """List tasks assigned to the current user, with optional filters."""
        tareas = await self._tarea_repo.list_por_asignado(
            self._current_user.id,
            estado=estado,
            materia_id=materia_id,
        )

        items: list[TareaMiaResponse] = []
        for t in tareas:
            ultimo = await self._coment_repo.list_por_tarea(t.id)
            items.append(TareaMiaResponse(
                id=t.id,
                materia_id=t.materia_id,
                asignado_por=t.asignado_por,
                estado=t.estado,
                descripcion=t.descripcion,
                ultimo_comentario=ultimo[-1].texto if ultimo else None,
                created_at=t.created_at,
                updated_at=t.updated_at,
            ))

        return TareaListResponse(items=items, total=len(items))  # type: ignore[arg-type]

    # ── Admin list ────────────────────────────────────────────────────────

    async def listar_admin(
        self,
        asignado_a: uuid.UUID | None = None,
        asignado_por: uuid.UUID | None = None,
        materia_id: uuid.UUID | None = None,
        estado: str | None = None,
        q: str | None = None,
    ) -> TareaListResponse:
        """List all tasks in the tenant (admin scope only).
        
        Raises 403 if current user is not COORDINADOR/ADMIN.
        """
        if not self._is_admin():
            raise HTTPException(status_code=403, detail="Forbidden")

        tareas = await self._tarea_repo.list_con_filtros(
            tenant_id=self._tenant_id,
            asignado_a=asignado_a,
            asignado_por=asignado_por,
            materia_id=materia_id,
            estado=estado,
            q=q,
        )

        items = [self._to_response(t) for t in tareas]
        return TareaListResponse(items=items, total=len(items))  # type: ignore[arg-type]

    # ── Cambiar estado ────────────────────────────────────────────────────

    async def cambiar_estado(
        self, tarea_id: uuid.UUID, data: TareaEstadoUpdateRequest,
    ) -> TareaResponse:
        """Change task state with transition validation."""
        tarea = await self._get_tarea_or_404(tarea_id)

        # Scope: TUTOR/PROFESOR can only change their own tasks
        if not self._is_admin() and tarea.asignado_a != self._current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        _validar_transicion(tarea.estado, data.estado)

        updated = await self._tarea_repo.update(tarea_id, estado=data.estado)
        assert updated is not None

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="TAREA_ESTADO",
            detalle={
                "tarea_id": str(tarea_id),
                "anterior": tarea.estado,
                "nuevo": data.estado,
            },
        )
        return self._to_response(updated)

    # ── Reasignar ─────────────────────────────────────────────────────────

    async def reasignar(
        self, tarea_id: uuid.UUID, data: TareaReasignarRequest,
    ) -> TareaResponse:
        """Reassign a task to a different user with audit trail."""
        tarea = await self._get_tarea_or_404(tarea_id)

        # Scope check
        if not self._is_admin() and tarea.asignado_a != self._current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        viejo = tarea.asignado_a
        updated = await self._tarea_repo.update(tarea_id, asignado_a=data.asignado_a)
        assert updated is not None

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="TAREA_REASIGNAR",
            detalle={
                "tarea_id": str(tarea_id),
                "anterior_asignado": str(viejo),
                "nuevo_asignado": str(data.asignado_a),
            },
        )
        return self._to_response(updated)

    # ── Comentarios ───────────────────────────────────────────────────────

    async def agregar_comentario(
        self, tarea_id: uuid.UUID, data: ComentarioCrearRequest,
    ) -> ComentarioResponse:
        """Add a comment to a task."""
        tarea = await self._get_tarea_or_404(tarea_id)

        # Scope: must own the task or be admin
        if not self._is_admin() and tarea.asignado_a != self._current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        comentario = await self._coment_repo.create(
            tarea_id=tarea_id,
            autor_id=self._current_user.id,
            texto=data.texto,
        )
        await self._db.flush()

        return ComentarioResponse(
            id=comentario.id,
            tarea_id=comentario.tarea_id,
            autor_id=comentario.autor_id,
            texto=comentario.texto,
            creado_at=comentario.creado_at,
        )

    async def listar_comentarios(
        self, tarea_id: uuid.UUID,
    ) -> ComentarioListResponse:
        """List all comments for a task (ASC by creado_at)."""
        await self._get_tarea_or_404(tarea_id)

        comentarios = await self._coment_repo.list_por_tarea(tarea_id)
        items = [
            ComentarioResponse(
                id=c.id,
                tarea_id=c.tarea_id,
                autor_id=c.autor_id,
                texto=c.texto,
                creado_at=c.creado_at,
            )
            for c in comentarios
        ]
        return ComentarioListResponse(items=items, total=len(items))

    # ── Helper ─────────────────────────────────────────────────────────────

    def _to_response(self, tarea: Tarea) -> TareaResponse:
        return TareaResponse(
            id=tarea.id,
            materia_id=tarea.materia_id,
            asignado_a=tarea.asignado_a,
            asignado_por=tarea.asignado_por,
            estado=tarea.estado,
            descripcion=tarea.descripcion,
            contexto_id=tarea.contexto_id,
            created_at=tarea.created_at,
            updated_at=tarea.updated_at,
        )
