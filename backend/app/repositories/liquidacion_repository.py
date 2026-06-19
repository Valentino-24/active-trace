"""Liquidacion and Factura repositories."""

from __future__ import annotations

import uuid
from typing import Sequence

from app.models.liquidacion import Liquidacion
from app.models.factura import Factura
from app.repositories.base import BaseRepository


class LiquidacionRepository(BaseRepository[Liquidacion]):
    _model_cls = Liquidacion

    async def list_por_periodo(
        self, *, cohorte_id: uuid.UUID, periodo: str,
    ) -> Sequence[Liquidacion]:
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Liquidacion.cohorte_id == cohorte_id)
            .where(Liquidacion.periodo == periodo)
            .order_by(Liquidacion.rol, Liquidacion.usuario_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_historial(self) -> Sequence[Liquidacion]:
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Liquidacion.estado == "Cerrada")
            .order_by(Liquidacion.periodo.desc(), Liquidacion.usuario_id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()


class FacturaRepository(BaseRepository[Factura]):
    _model_cls = Factura

    async def list_con_filtros(
        self, *,
        usuario_id: uuid.UUID | None = None,
        estado: str | None = None,
    ) -> Sequence[Factura]:
        stmt = self._exclude_deleted(self._stmt())
        if usuario_id is not None:
            stmt = stmt.where(Factura.usuario_id == usuario_id)
        if estado is not None:
            stmt = stmt.where(Factura.estado == estado)
        stmt = stmt.order_by(Factura.cargada_at.desc())
        result = await self._session.execute(stmt)
        return result.scalars().all()
