"""Perfil and Inbox router."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.perfil_inbox import (
    PerfilUpdateRequest, PerfilResponse,
    MensajeEnviarRequest, MensajeResponse, MensajeListResponse,
)
from app.services.perfil_inbox_service import PerfilInboxService

router = APIRouter(tags=["perfil-inbox"])


@router.get("/api/perfil", response_model=PerfilResponse)
async def ver_perfil(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = PerfilInboxService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.ver_perfil()


@router.patch("/api/perfil", response_model=PerfilResponse)
async def actualizar_perfil(
    body: PerfilUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = PerfilInboxService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.actualizar_perfil(body)


@router.post("/api/inbox/enviar", response_model=MensajeResponse, status_code=201)
async def enviar_mensaje(
    body: MensajeEnviarRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = PerfilInboxService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.enviar_mensaje(body)


@router.get("/api/inbox/recibidos", response_model=MensajeListResponse)
async def listar_recibidos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = PerfilInboxService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_recibidos()


@router.get("/api/inbox/enviados", response_model=MensajeListResponse)
async def listar_enviados(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = PerfilInboxService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.listar_enviados()


@router.patch("/api/inbox/{mensaje_id}/leido", response_model=MensajeResponse)
async def marcar_leido(
    mensaje_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = PerfilInboxService(db=db, tenant_id=current_user.tenant_id, current_user=current_user)
    return await svc.marcar_leido(mensaje_id)
