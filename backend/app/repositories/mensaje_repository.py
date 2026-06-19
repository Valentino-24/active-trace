"""Mensaje repository — internal messaging."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select

from app.models.mensaje import Mensaje
from app.repositories.base import BaseRepository


class MensajeRepository(BaseRepository[Mensaje]):
    _model_cls = Mensaje

    async def list_recibidos(self, destinatario_id: uuid.UUID) -> Sequence[Mensaje]:
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Mensaje.destinatario_id == destinatario_id)
            .order_by(Mensaje.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_enviados(self, remitente_id: uuid.UUID) -> Sequence[Mensaje]:
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Mensaje.remitente_id == remitente_id)
            .order_by(Mensaje.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def marcar_leido(self, mensaje_id: uuid.UUID) -> None:
        msg = await self.get(mensaje_id)
        if msg and not msg.leido:
            msg.leido = True
            msg.leido_at = datetime.now(UTC)
            await self._session.flush()
