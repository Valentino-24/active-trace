"""Liquidacion service — honorarium calculation, grille management, and billing."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asignacion import Asignacion
from app.models.materia import Materia
from app.models.user import User
from app.repositories.salario_repository import SalarioBaseRepository, SalarioPlusRepository
from app.repositories.liquidacion_repository import LiquidacionRepository, FacturaRepository
from app.schemas.liquidaciones import (
    SalarioBaseCrearRequest, SalarioBaseUpdateRequest, SalarioBaseResponse,
    SalarioPlusCrearRequest, SalarioPlusResponse,
    LiquidacionCalcularRequest, LiquidacionResponse, LiquidacionListResponse,
    FacturaCrearRequest, FacturaResponse,
)
from app.services.audit_service import log_action


class LiquidacionService:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._salario_base_repo = SalarioBaseRepository(session=db, tenant_id=tenant_id)
        self._salario_plus_repo = SalarioPlusRepository(session=db, tenant_id=tenant_id)
        self._liquidacion_repo = LiquidacionRepository(session=db, tenant_id=tenant_id)
        self._factura_repo = FacturaRepository(session=db, tenant_id=tenant_id)

    # ── SalarioBase CRUD ────────────────────────────────────────────────────

    async def crear_salario_base(self, data: SalarioBaseCrearRequest) -> SalarioBaseResponse:
        sb = await self._salario_base_repo.create(
            rol=data.rol, monto=data.monto, desde=data.desde, hasta=data.hasta,
        )
        await self._db.flush()
        return SalarioBaseResponse(id=sb.id, rol=sb.rol, monto=sb.monto, desde=sb.desde, hasta=sb.hasta)

    async def listar_salarios_base(self) -> list[SalarioBaseResponse]:
        items = await self._salario_base_repo.list()
        return [SalarioBaseResponse(id=s.id, rol=s.rol, monto=s.monto, desde=s.desde, hasta=s.hasta) for s in items]

    async def actualizar_salario_base(self, sb_id: uuid.UUID, data: SalarioBaseUpdateRequest) -> SalarioBaseResponse:
        sb = await self._salario_base_repo.get(sb_id)
        if sb is None:
            raise HTTPException(404, "Salario base no encontrado")
        updates = {k: v for k, v in {"monto": data.monto, "hasta": data.hasta}.items() if v is not None}
        if updates:
            await self._salario_base_repo.update(sb_id, **updates)
        return SalarioBaseResponse(id=sb.id, rol=sb.rol, monto=sb.monto, desde=sb.desde, hasta=sb.hasta)

    async def eliminar_salario_base(self, sb_id: uuid.UUID) -> None:
        if await self._salario_base_repo.get(sb_id) is None:
            raise HTTPException(404, "Salario base no encontrado")
        await self._salario_base_repo.soft_delete(sb_id)

    # ── SalarioPlus CRUD ────────────────────────────────────────────────────

    async def crear_salario_plus(self, data: SalarioPlusCrearRequest) -> SalarioPlusResponse:
        sp = await self._salario_plus_repo.create(
            grupo=data.grupo, rol=data.rol, descripcion=data.descripcion,
            monto=data.monto, desde=data.desde, hasta=data.hasta,
        )
        await self._db.flush()
        return SalarioPlusResponse(id=sp.id, grupo=sp.grupo, rol=sp.rol, descripcion=sp.descripcion,
                                    monto=sp.monto, desde=sp.desde, hasta=sp.hasta)

    async def listar_salarios_plus(self) -> list[SalarioPlusResponse]:
        items = await self._salario_plus_repo.list_all()
        return [SalarioPlusResponse(id=s.id, grupo=s.grupo, rol=s.rol, descripcion=s.descripcion,
                                     monto=s.monto, desde=s.desde, hasta=s.hasta) for s in items]

    async def eliminar_salario_plus(self, sp_id: uuid.UUID) -> None:
        if await self._salario_plus_repo.get(sp_id) is None:
            raise HTTPException(404, "Salario plus no encontrado")
        await self._salario_plus_repo.soft_delete(sp_id)

    # ── Liquidacion: calcular ──────────────────────────────────────────────

    async def calcular(self, data: LiquidacionCalcularRequest) -> LiquidacionListResponse:
        periodo_date = date(int(data.periodo.split("-")[0]), int(data.periodo.split("-")[1]), 1)

        # Get active asignaciones in cohorte
        stmt = (
            select(Asignacion)
            .where(Asignacion.cohorte_id == data.cohorte_id)
            .where(Asignacion.tenant_id == self._tenant_id)
            .where(Asignacion.deleted_at.is_(None))
        )
        result = await self._db.execute(stmt)
        asignaciones = result.scalars().all()

        # Group by usuario
        usuarios: dict[uuid.UUID, dict] = {}
        for a in asignaciones:
            if a.usuario_id not in usuarios:
                usuarios[a.usuario_id] = {"rol": a.rol, "materia_ids": set()}
            if a.materia_id:
                usuarios[a.usuario_id]["materia_ids"].add(a.materia_id)

        items = []
        for user_id, info in usuarios.items():
            rol = info["rol"]
            base_sb = await self._salario_base_repo.get_vigente(rol=rol, fecha=periodo_date)
            monto_base = base_sb.monto if base_sb else Decimal("0")

            # Get distinct grupo_plus from materias
            grupos: set[str] = set()
            if info["materia_ids"]:
                mat_stmt = (
                    select(Materia.grupo_plus)
                    .where(Materia.id.in_(info["materia_ids"]))
                    .where(Materia.grupo_plus.isnot(None))
                    .distinct()
                )
                mat_result = await self._db.execute(mat_stmt)
                for row in mat_result.fetchall():
                    if row[0]:
                        grupos.add(row[0])

            monto_plus = Decimal("0")
            for grupo in grupos:
                pluses = await self._salario_plus_repo.get_vigentes_por_grupo_rol(
                    grupo=grupo, rol=rol, fecha=periodo_date,
                )
                for p in pluses:
                    monto_plus += p.monto

            total = monto_base + monto_plus
            es_nexo = rol == "NEXO"

            # Check if user is facturador
            user = await self._db.get(User, user_id)
            facturador = user.facturador if user else False

            liq = await self._liquidacion_repo.create(
                cohorte_id=data.cohorte_id, periodo=data.periodo,
                usuario_id=user_id, rol=rol,
                monto_base=monto_base, monto_plus=monto_plus, total=total,
                es_nexo=es_nexo, excluido_por_factura=facturador,
                estado="Abierta",
            )
            items.append(liq)

        await self._db.flush()
        await log_action(self._db, self._tenant_id, self._current_user.id,
                         "LIQUIDACION_CALCULAR",
                         detalle={"cohorte_id": str(data.cohorte_id), "periodo": data.periodo,
                                   "cantidad": len(items)})

        return LiquidacionListResponse(
            items=[LiquidacionResponse(
                id=li.id, cohorte_id=li.cohorte_id, periodo=li.periodo,
                usuario_id=li.usuario_id, rol=li.rol,
                monto_base=li.monto_base, monto_plus=li.monto_plus, total=li.total,
                es_nexo=li.es_nexo, excluido_por_factura=li.excluido_por_factura,
                estado=li.estado,
            ) for li in items],
            total=len(items),
        )

    async def cerrar(self, liquidacion_id: uuid.UUID) -> LiquidacionResponse:
        liq = await self._liquidacion_repo.get(liquidacion_id)
        if liq is None:
            raise HTTPException(404, "Liquidacion no encontrada")
        if liq.estado == "Cerrada":
            raise HTTPException(409, "Liquidacion ya se encuentra cerrada")
        await self._liquidacion_repo.update(liquidacion_id, estado="Cerrada")
        await log_action(self._db, self._tenant_id, self._current_user.id,
                         "LIQUIDACION_CERRAR", detalle={"liquidacion_id": str(liquidacion_id)})
        return LiquidacionResponse(
            id=liq.id, cohorte_id=liq.cohorte_id, periodo=liq.periodo,
            usuario_id=liq.usuario_id, rol=liq.rol,
            monto_base=liq.monto_base, monto_plus=liq.monto_plus, total=liq.total,
            es_nexo=liq.es_nexo, excluido_por_factura=liq.excluido_por_factura,
            estado="Cerrada",
        )

    async def listar_historial(self) -> LiquidacionListResponse:
        items = await self._liquidacion_repo.list_historial()
        return LiquidacionListResponse(
            items=[LiquidacionResponse(
                id=li.id, cohorte_id=li.cohorte_id, periodo=li.periodo,
                usuario_id=li.usuario_id, rol=li.rol,
                monto_base=li.monto_base, monto_plus=li.monto_plus, total=li.total,
                es_nexo=li.es_nexo, excluido_por_factura=li.excluido_por_factura,
                estado=li.estado,
            ) for li in items],
            total=len(items),
        )

    # ── Facturas ───────────────────────────────────────────────────────────

    async def crear_factura(self, data: FacturaCrearRequest) -> FacturaResponse:
        f = await self._factura_repo.create(
            usuario_id=data.usuario_id, periodo=data.periodo, detalle=data.detalle,
            referencia_archivo=data.referencia_archivo,
            cargada_at=datetime.now(UTC),
        )
        await self._db.flush()
        return FacturaResponse(id=f.id, usuario_id=f.usuario_id, periodo=f.periodo,
                                detalle=f.detalle, referencia_archivo=f.referencia_archivo,
                                estado=f.estado, abonada_at=f.abonada_at, cargada_at=f.cargada_at)

    async def listar_facturas(self, usuario_id: uuid.UUID | None = None,
                               estado: str | None = None) -> list[FacturaResponse]:
        items = await self._factura_repo.list_con_filtros(usuario_id=usuario_id, estado=estado)
        return [FacturaResponse(id=f.id, usuario_id=f.usuario_id, periodo=f.periodo,
                                 detalle=f.detalle, referencia_archivo=f.referencia_archivo,
                                 estado=f.estado, abonada_at=f.abonada_at, cargada_at=f.cargada_at)
                for f in items]

    async def abonar_factura(self, factura_id: uuid.UUID) -> FacturaResponse:
        f = await self._factura_repo.get(factura_id)
        if f is None:
            raise HTTPException(404, "Factura no encontrada")
        await self._factura_repo.update(factura_id, estado="Abonada", abonada_at=datetime.now(UTC))
        return FacturaResponse(id=f.id, usuario_id=f.usuario_id, periodo=f.periodo,
                                detalle=f.detalle, referencia_archivo=f.referencia_archivo,
                                estado="Abonada", abonada_at=datetime.now(UTC), cargada_at=f.cargada_at)
