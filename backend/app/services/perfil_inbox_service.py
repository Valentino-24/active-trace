"""Perfil and Inbox service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.repositories.mensaje_repository import MensajeRepository
from app.schemas.perfil_inbox import (
    PerfilUpdateRequest, PerfilResponse,
    MensajeEnviarRequest, MensajeResponse, MensajeListResponse,
)


class PerfilInboxService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._mensaje_repo = MensajeRepository(session=db, tenant_id=tenant_id)

    # ── Perfil ──────────────────────────────────────────────────────

    async def ver_perfil(self) -> PerfilResponse:
        return PerfilResponse(
            id=self._current_user.id, email=self._current_user.email,
            display_name=self._current_user.display_name,
            cuil=getattr(self._current_user, "cuil", None),
        )

    async def actualizar_perfil(self, data: PerfilUpdateRequest) -> PerfilResponse:
        if data.display_name is not None:
            self._current_user.display_name = data.display_name
            await self._db.flush()
        return await self.ver_perfil()

    # ── Inbox ───────────────────────────────────────────────────────

    async def enviar_mensaje(self, data: MensajeEnviarRequest) -> MensajeResponse:
        msg = await self._mensaje_repo.create(
            remitente_id=self._current_user.id,
            destinatario_id=data.destinatario_id,
            asunto=data.asunto, texto=data.texto,
        )
        await self._db.flush()
        return self._to_msg(msg)

    async def listar_recibidos(self) -> MensajeListResponse:
        msgs = await self._mensaje_repo.list_recibidos(self._current_user.id)
        return MensajeListResponse(items=[self._to_msg(m) for m in msgs], total=len(msgs))

    async def listar_enviados(self) -> MensajeListResponse:
        msgs = await self._mensaje_repo.list_enviados(self._current_user.id)
        return MensajeListResponse(items=[self._to_msg(m) for m in msgs], total=len(msgs))

    async def marcar_leido(self, mensaje_id: uuid.UUID) -> MensajeResponse:
        msg = await self._mensaje_repo.get(mensaje_id)
        if msg is None:
            raise HTTPException(404, "Mensaje no encontrado")
        if msg.destinatario_id != self._current_user.id:
            raise HTTPException(403, "Forbidden")
        await self._mensaje_repo.marcar_leido(mensaje_id)
        return self._to_msg(msg)

    def _to_msg(self, m) -> MensajeResponse:
        return MensajeResponse(
            id=m.id, remitente_id=m.remitente_id, destinatario_id=m.destinatario_id,
            asunto=m.asunto, texto=m.texto, leido=m.leido, leido_at=m.leido_at,
            created_at=m.created_at,
        )
