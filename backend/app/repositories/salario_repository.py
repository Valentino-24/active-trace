"""Salario repositories — base salary and plus supplements with temporal validity."""

from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import Sequence

from sqlalchemy import and_, or_, select

from app.models.salario_base import SalarioBase
from app.models.salario_plus import SalarioPlus
from app.repositories.base import BaseRepository


class SalarioBaseRepository(BaseRepository[SalarioBase]):
    _model_cls = SalarioBase

    async def get_vigente(self, *, rol: str, fecha: date_type) -> SalarioBase | None:
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(SalarioBase.rol == rol)
            .where(SalarioBase.desde <= fecha)
            .where(or_(SalarioBase.hasta.is_(None), SalarioBase.hasta >= fecha))
            .order_by(SalarioBase.desde.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class SalarioPlusRepository(BaseRepository[SalarioPlus]):
    _model_cls = SalarioPlus

    async def get_vigentes_por_grupo_rol(
        self, *, grupo: str, rol: str, fecha: date_type,
    ) -> Sequence[SalarioPlus]:
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(SalarioPlus.grupo == grupo)
            .where(SalarioPlus.rol == rol)
            .where(SalarioPlus.desde <= fecha)
            .where(or_(SalarioPlus.hasta.is_(None), SalarioPlus.hasta >= fecha))
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[SalarioPlus]:
        stmt = self._exclude_deleted(self._stmt()).order_by(SalarioPlus.grupo)
        result = await self._session.execute(stmt)
        return result.scalars().all()
