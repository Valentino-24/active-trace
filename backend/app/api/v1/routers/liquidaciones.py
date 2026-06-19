"""Liquidaciones y Honorarios router — salary, liquidation, and billing endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.liquidaciones import (
    SalarioBaseCrearRequest, SalarioBaseUpdateRequest, SalarioBaseResponse,
    SalarioPlusCrearRequest, SalarioPlusResponse,
    LiquidacionCalcularRequest, LiquidacionResponse, LiquidacionListResponse,
    FacturaCrearRequest, FacturaResponse,
)
from app.services.liquidacion_service import LiquidacionService

router = APIRouter(tags=["liquidaciones"])

_G_CONFIG = Depends(require_permission("liquidaciones:configurar-salarios"))
_G_GESTION = Depends(require_permission("liquidaciones:gestionar"))


# ── SalarioBase ────────────────────────────────────────────────────────────

@router.post("/api/salarios/base", response_model=SalarioBaseResponse, status_code=201,
             dependencies=[_G_CONFIG])
async def crear_salario_base(body: SalarioBaseCrearRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.crear_salario_base(body)

@router.get("/api/salarios/base", response_model=list[SalarioBaseResponse], dependencies=[_G_CONFIG])
async def listar_salarios_base(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_salarios_base()

@router.patch("/api/salarios/base/{sb_id}", response_model=SalarioBaseResponse, dependencies=[_G_CONFIG])
async def actualizar_salario_base(sb_id: uuid.UUID, body: SalarioBaseUpdateRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.actualizar_salario_base(sb_id, body)

@router.delete("/api/salarios/base/{sb_id}", status_code=200, dependencies=[_G_CONFIG])
async def eliminar_salario_base(sb_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    await svc.eliminar_salario_base(sb_id)
    return {"detail": "Eliminado"}


# ── SalarioPlus ──────────────────────────────────────────────────────────────

@router.post("/api/salarios/plus", response_model=SalarioPlusResponse, status_code=201,
             dependencies=[_G_CONFIG])
async def crear_salario_plus(body: SalarioPlusCrearRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.crear_salario_plus(body)

@router.get("/api/salarios/plus", response_model=list[SalarioPlusResponse], dependencies=[_G_CONFIG])
async def listar_salarios_plus(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_salarios_plus()

@router.delete("/api/salarios/plus/{sp_id}", status_code=200, dependencies=[_G_CONFIG])
async def eliminar_salario_plus(sp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    await svc.eliminar_salario_plus(sp_id)
    return {"detail": "Eliminado"}


# ── Liquidaciones ──────────────────────────────────────────────────────────

@router.post("/api/liquidaciones/calcular", response_model=LiquidacionListResponse,
             status_code=201, dependencies=[_G_GESTION])
async def calcular_liquidacion(body: LiquidacionCalcularRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.calcular(body)

@router.patch("/api/liquidaciones/{liq_id}/cerrar", response_model=LiquidacionResponse,
              dependencies=[_G_GESTION])
async def cerrar_liquidacion(liq_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.cerrar(liq_id)

@router.get("/api/liquidaciones/historial", response_model=LiquidacionListResponse,
            dependencies=[Depends(require_permission("liquidaciones:ver"))])
async def historial_liquidaciones(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_historial()


# ── Facturas ────────────────────────────────────────────────────────────────

@router.post("/api/facturas", response_model=FacturaResponse, status_code=201,
             dependencies=[_G_GESTION])
async def crear_factura(body: FacturaCrearRequest,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.crear_factura(body)

@router.get("/api/facturas", response_model=list[FacturaResponse], dependencies=[_G_GESTION])
async def listar_facturas(
    usuario_id: uuid.UUID | None = Query(default=None),
    estado: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_facturas(usuario_id=usuario_id, estado=estado)

@router.patch("/api/facturas/{factura_id}/abonar", response_model=FacturaResponse,
              dependencies=[_G_GESTION])
async def abonar_factura(factura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    svc = LiquidacionService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.abonar_factura(factura_id)
