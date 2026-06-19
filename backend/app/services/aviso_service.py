"""Aviso service — CRUD, visibility filtering, and acknowledgment logic.

Implements:
    - RN-18: validity window (inicio_en <= ahora <= fin_en)
    - RN-19: read acknowledgment exclusion
    - RN-20: audience scope filtering (alcance)
    - Audit: AVISO_CREAR, AVISO_MODIFICAR, AVISO_ELIMINAR, AVISO_ACK
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.asignacion import Asignacion
from app.models.aviso import Aviso
from app.models.user import User
from app.repositories.aviso_repository import AcknowledgmentRepository, AvisoRepository
from app.schemas.avisos import (
    AckItem,
    AckResponse,
    AcksListResponse,
    AvisoCrearRequest,
    AvisoListResponse,
    AvisoResponse,
    AvisoUpdateRequest,
    MisAvisoItem,
    MisAvisosResponse,
)
from app.services.audit_service import log_action


class AvisoService:
    """Service for institutional notice board operations."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._aviso_repo = AvisoRepository(session=db, tenant_id=tenant_id)
        self._ack_repo = AcknowledgmentRepository(session=db, tenant_id=tenant_id)

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _get_aviso_or_404(self, aviso_id: uuid.UUID) -> Aviso:
        """Fetch a non-deleted aviso by id or raise 404."""
        aviso = await self._aviso_repo.get(aviso_id)
        if aviso is None:
            raise HTTPException(status_code=404, detail="Aviso no encontrado")
        return aviso

    # ── Gestión: crear ─────────────────────────────────────────────────────────

    async def crear(self, data: AvisoCrearRequest) -> AvisoResponse:
        """Create a new notice.

        Raises 422 if validity window is invalid (inicio_en >= fin_en).
        """
        if data.inicio_en >= data.fin_en:
            raise HTTPException(
                status_code=422,
                detail="La fecha de inicio debe ser anterior a la fecha de fin",
            )

        aviso = await self._aviso_repo.create(
            titulo=data.titulo,
            cuerpo=data.cuerpo,
            alcance=data.alcance,
            materia_id=data.materia_id,
            cohorte_id=data.cohorte_id,
            rol_destino=data.rol_destino,
            severidad=data.severidad,
            inicio_en=data.inicio_en,
            fin_en=data.fin_en,
            orden=data.orden,
            activo=True,
            requiere_ack=data.requiere_ack,
        )

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="AVISO_CREAR",
            detalle={
                "aviso_id": str(aviso.id),
                "titulo": aviso.titulo,
                "alcance": aviso.alcance,
            },
        )

        return AvisoResponse(
            id=aviso.id,
            titulo=aviso.titulo,
            alcance=aviso.alcance,
            severidad=aviso.severidad,
            activo=aviso.activo,
            inicio_en=aviso.inicio_en,
            fin_en=aviso.fin_en,
            orden=aviso.orden,
            requiere_ack=aviso.requiere_ack,
            created_at=aviso.created_at,
            total_vistos=0,
            total_acks=0,
        )

    # ── Gestión: actualizar ────────────────────────────────────────────────────

    async def actualizar(
        self, aviso_id: uuid.UUID, data: AvisoUpdateRequest,
    ) -> AvisoResponse:
        """Partially update a notice.

        Only fields with non-None values are applied.
        """
        aviso = await self._get_aviso_or_404(aviso_id)

        update_fields: dict[str, Any] = {}
        for field_name in data.model_fields_set:
            value = getattr(data, field_name)
            if value is not None:
                update_fields[field_name] = value

        if not update_fields:
            raise HTTPException(
                status_code=422,
                detail="No se enviaron campos para actualizar",
            )

        # Validate window if both dates provided
        new_inicio = update_fields.get("inicio_en", aviso.inicio_en)
        new_fin = update_fields.get("fin_en", aviso.fin_en)
        if new_inicio >= new_fin:
            raise HTTPException(
                status_code=422,
                detail="La fecha de inicio debe ser anterior a la fecha de fin",
            )

        updated = await self._aviso_repo.update(aviso_id, **update_fields)
        if updated is None:  # pragma: no cover — race condition guard
            raise HTTPException(status_code=404, detail="Aviso no encontrado")

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="AVISO_MODIFICAR",
            detalle={
                "aviso_id": str(aviso.id),
                "campos": list(update_fields.keys()),
            },
        )

        return await self._to_response(updated)

    # ── Gestión: eliminar (soft delete) ────────────────────────────────────────

    async def eliminar(self, aviso_id: uuid.UUID) -> None:
        """Soft-delete a notice."""
        # Raises 404 if not found
        await self._get_aviso_or_404(aviso_id)
        await self._aviso_repo.soft_delete(aviso_id)

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="AVISO_ELIMINAR",
            detalle={"aviso_id": str(aviso_id)},
        )

    # ── Gestión: listar con contadores ─────────────────────────────────────────

    async def listar_gestion(self) -> AvisoListResponse:
        """List all non-deleted notices with derived acknowledgment counters."""
        rows = await self._aviso_repo.list_con_contadores()
        items = [AvisoResponse(**row) for row in rows]
        return AvisoListResponse(items=items, total=len(items))

    # ── Destinatario: mis avisos ───────────────────────────────────────────────

    async def listar_mis_avisos(self) -> MisAvisosResponse:
        """List active notices visible to the current user.

        Applies:
            - RN-18: validity window filter
            - RN-20: audience scope (Global, PorMateria, PorCohorte, PorRol)
            - RN-19: exclude already-acked notices (if requiere_ack=True)
        """
        ahora = datetime.now(UTC)
        user_id = self._current_user.id

        # Gather user's roles, asignaciones, and cohortes
        role_codes = await self._get_user_role_codes()
        materia_ids = await self._get_user_materia_ids()
        cohorte_ids = await self._get_user_cohorte_ids()

        avisos = await self._aviso_repo.list_activos_para_usuario(
            usuario_id=user_id,
            roles=role_codes,
            materias_ids=materia_ids,
            cohorte_ids=cohorte_ids,
        )

        # Check which avisos have been acknowledged by this user
        acked_ids: set[uuid.UUID] = set()
        for aviso in avisos:
            if aviso.requiere_ack:
                exists = await self._ack_repo.exists_por_usuario(
                    aviso_id=aviso.id, usuario_id=user_id,
                )
                if exists:
                    acked_ids.add(aviso.id)

        items = [
            MisAvisoItem(
                id=aviso.id,
                titulo=aviso.titulo,
                cuerpo=aviso.cuerpo,
                severidad=aviso.severidad,
                orden=aviso.orden,
                requiere_ack=aviso.requiere_ack,
                ya_ack=aviso.id in acked_ids,
            )
            for aviso in avisos
            # RN-19: if requiere_ack and user already acked, exclude
            if not (aviso.requiere_ack and aviso.id in acked_ids)
        ]

        return MisAvisosResponse(items=items)

    async def _get_user_role_codes(self) -> list[str]:
        """Get current user's role codes within this tenant."""
        from app.models.rbac import UserRole as UserRoleModel

        stmt = (
            select(UserRoleModel)
            .where(
                UserRoleModel.user_id == self._current_user.id,
                UserRoleModel.tenant_id == self._tenant_id,
            )
            .options(joinedload(UserRoleModel.role))
        )
        result = await self._db.execute(stmt)
        return [ur.role.codigo for ur in result.scalars().all() if ur.role]

    async def _get_user_materia_ids(self) -> list[uuid.UUID]:
        """Get materia ids the user is assigned to within this tenant."""
        stmt = (
            select(Asignacion.materia_id)
            .where(
                Asignacion.usuario_id == self._current_user.id,
                Asignacion.tenant_id == self._tenant_id,
                Asignacion.deleted_at.is_(None),
            )
            .distinct()
        )
        result = await self._db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def _get_user_cohorte_ids(self) -> list[uuid.UUID]:
        """Get cohorte ids the user belongs to via their asignaciones."""
        stmt = (
            select(Asignacion.cohorte_id)
            .where(
                Asignacion.usuario_id == self._current_user.id,
                Asignacion.tenant_id == self._tenant_id,
                Asignacion.cohorte_id.isnot(None),
                Asignacion.deleted_at.is_(None),
            )
            .distinct()
        )
        result = await self._db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    # ── Acknowledgment ────────────────────────────────────────────────────────

    async def ack(self, aviso_id: uuid.UUID) -> AckResponse:
        """Acknowledge (confirm receipt of) a notice.

        Raises 409 if:
            - The notice does not require acknowledgment.
            - The user has already acknowledged this notice.
        """
        aviso = await self._get_aviso_or_404(aviso_id)

        if not aviso.requiere_ack:
            raise HTTPException(
                status_code=409,
                detail="Este aviso no requiere confirmación",
            )

        exists = await self._ack_repo.exists_por_usuario(
            aviso_id=aviso_id, usuario_id=self._current_user.id,
        )
        if exists:
            raise HTTPException(
                status_code=409,
                detail="Ya has confirmado este aviso",
            )

        record = await self._ack_repo.create(
            aviso_id=aviso_id,
            usuario_id=self._current_user.id,
        )

        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="AVISO_ACK",
            detalle={
                "aviso_id": str(aviso_id),
                "ack_id": str(record.id),
            },
        )

        return AckResponse(
            id=record.id,
            aviso_id=record.aviso_id,
            confirmado_at=record.confirmado_at,
        )

    async def listar_acks(self, aviso_id: uuid.UUID) -> AcksListResponse:
        """List all acknowledgments for a specific notice (management view)."""
        aviso = await self._get_aviso_or_404(aviso_id)
        _ = aviso  # ensure aviso exists

        records = await self._ack_repo.list_por_aviso(aviso_id)

        # Fetch user emails for display
        items = []
        for rec in records:
            email = await self._get_user_email(rec.usuario_id)
            items.append(AckItem(
                usuario_id=rec.usuario_id,
                usuario_email=email,
                confirmado_at=rec.confirmado_at,
            ))

        return AcksListResponse(items=items, total=len(items))

    async def _get_user_email(self, user_id: uuid.UUID) -> str:
        """Fetch a user's email by id."""
        from app.models.user import User as UserModel

        stmt = select(UserModel.email).where(UserModel.id == user_id)
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        return row or ""

    # ── Helpers internos ───────────────────────────────────────────────────────

    async def _to_response(self, aviso: Aviso) -> AvisoResponse:
        """Convert an Aviso instance to a response schema with counters."""
        total_acks = await self._ack_repo.count_por_aviso(aviso.id)
        return AvisoResponse(
            id=aviso.id,
            titulo=aviso.titulo,
            alcance=aviso.alcance,
            severidad=aviso.severidad,
            activo=aviso.activo,
            inicio_en=aviso.inicio_en,
            fin_en=aviso.fin_en,
            orden=aviso.orden,
            requiere_ack=aviso.requiere_ack,
            created_at=aviso.created_at,
            total_vistos=total_acks,
            total_acks=total_acks,
        )
