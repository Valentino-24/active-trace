"""Coloquios router — convocatorias, reservas, notas, métricas.

Endpoints are organized in three groups:
- Gestión (guard: coloquios:gestionar): crear, importar, cerrar, registrar notas
- Consulta (guard: coloquios:ver): listar, métricas, agenda, registro
- Alumno (guard: rol ALUMNO): disponibles, reservar, mis reservas, cancelar
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.rbac import UserRole as UserRoleModel
from app.models.user import User
from app.schemas.coloquios import (
    AgendaResponse,
    ConvocatoriaDisponibleResponse,
    ConvocatoriaListResponse,
    EvaluacionCrearRequest,
    EvaluacionResponse,
    EvaluacionUpdateRequest,
    ImportarAlumnosRequest,
    ImportarAlumnosResponse,
    MetricasResponse,
    MisReservasResponse,
    RegistroResponse,
    ReservaRequest,
    ReservaResponse,
    ResultadoResponse,
    ResultadoUpdateRequest,
)
from app.services.coloquio_service import ColoquioService

router = APIRouter(tags=["coloquios"])


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _es_alumno(db: AsyncSession, user: User) -> bool:
    """Check if the user has the ALUMNO role."""
    stmt = (
        select(UserRoleModel)
        .where(
            UserRoleModel.user_id == user.id,
            UserRoleModel.tenant_id == user.tenant_id,
            UserRoleModel.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    for ur in result.scalars().all():
        if ur.role.codigo == "ALUMNO":
            return True
    return False


async def _require_alumno(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the user has the ALUMNO role."""
    if not await _es_alumno(db, current_user):
        raise HTTPException(status_code=403, detail="Se requiere rol ALUMNO")
    return current_user


# ── Gestión: Convocatorias (coloquios:gestionar) ─────────────────────────────


@router.post(
    "/api/coloquios",
    response_model=EvaluacionResponse,
    status_code=201,
    dependencies=[Depends(require_permission("coloquios:gestionar"))],
)
async def crear_convocatoria(
    body: EvaluacionCrearRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new evaluation convocation. (AT-01)"""
    # Validate tipo
    from app.schemas.coloquios import TIPO_EVALUACION_VALUES
    if body.tipo not in TIPO_EVALUACION_VALUES:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido: '{body.tipo}'. Debe ser uno de: {', '.join(sorted(TIPO_EVALUACION_VALUES))}",
        )

    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    ev = await service.crear_convocatoria(
        materia_id=body.materia_id,
        cohorte_id=body.cohorte_id,
        tipo=body.tipo,
        instancia=body.instancia,
        dias_disponibles=body.dias_disponibles,
    )
    return ev


@router.post(
    "/api/coloquios/{evaluacion_id}/alumnos",
    response_model=ImportarAlumnosResponse,
    dependencies=[Depends(require_permission("coloquios:gestionar"))],
)
async def importar_alumnos(
    evaluacion_id: uuid.UUID,
    body: ImportarAlumnosRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import students into a convocation. (AT-03, AT-04)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    return await service.importar_alumnos(
        evaluacion_id=evaluacion_id,
        alumno_ids=body.alumno_ids,
    )


@router.patch(
    "/api/coloquios/{evaluacion_id}",
    response_model=EvaluacionResponse,
    dependencies=[Depends(require_permission("coloquios:gestionar"))],
)
async def cerrar_convocatoria(
    evaluacion_id: uuid.UUID,
    body: EvaluacionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update/closes an evaluation convocation. (AT-06)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    ev = await service.get_evaluacion(evaluacion_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")

    # Apply updates
    update_kwargs = {}
    if body.activa is not None:
        update_kwargs["activa"] = body.activa
    if body.dias_disponibles is not None:
        update_kwargs["dias_disponibles"] = body.dias_disponibles
    if body.instancia is not None:
        update_kwargs["instancia"] = body.instancia

    from app.repositories.coloquio_repository import EvaluacionRepository
    repo = EvaluacionRepository(session=db, tenant_id=current_user.tenant_id)
    updated = await repo.update(evaluacion_id, **update_kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
    return updated


@router.patch(
    "/api/coloquios/resultados/{resultado_id}",
    response_model=ResultadoResponse,
    dependencies=[Depends(require_permission("coloquios:gestionar"))],
)
async def registrar_nota(
    resultado_id: uuid.UUID,
    body: ResultadoUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a final grade for a student. (AT-12)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    return await service.registrar_nota(
        resultado_id=resultado_id,
        nota_final=body.nota_final,
    )


# ── Consulta (coloquios:ver) ─────────────────────────────────────────────────


@router.get(
    "/api/coloquios",
    response_model=ConvocatoriaListResponse,
    dependencies=[Depends(require_permission("coloquios:ver"))],
)
async def listar_convocatorias(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all convocations with metrics. (AT-05)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    items = await service.listar_convocatorias()
    return ConvocatoriaListResponse(items=items, total=len(items))


@router.get(
    "/api/coloquios/metricas",
    response_model=MetricasResponse,
    dependencies=[Depends(require_permission("coloquios:ver"))],
)
async def get_metricas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregate metrics. (AT-13)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    return await service.get_metricas()


@router.get(
    "/api/coloquios/agenda",
    response_model=AgendaResponse,
    dependencies=[Depends(require_permission("coloquios:ver"))],
)
async def get_agenda(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get consolidated agenda of active reservations. (AT-14)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    items = await service.get_agenda()
    return AgendaResponse(items=items)


@router.get(
    "/api/coloquios/registro",
    response_model=RegistroResponse,
    dependencies=[Depends(require_permission("coloquios:ver"))],
)
async def get_registro(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get consolidated academic registry. (AT-15)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    items = await service.get_registro()
    return RegistroResponse(items=items)


# ── Alumno: disponibles ──────────────────────────────────────────────────────


@router.get(
    "/api/coloquios/disponibles",
    response_model=ConvocatoriaDisponibleResponse,
)
async def listar_disponibles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_alumno),
):
    """List active convocations where the student is habilitated. (AT-10)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    items = await service.listar_disponibles_para_alumno()
    return ConvocatoriaDisponibleResponse(items=items)


@router.post(
    "/api/coloquios/{evaluacion_id}/reservar",
    response_model=ReservaResponse,
    status_code=201,
)
async def reservar_turno(
    evaluacion_id: uuid.UUID,
    body: ReservaRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_alumno),
):
    """Reserve a slot in an evaluation. (AT-07, AT-08)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    return await service.reservar_turno(
        evaluacion_id=evaluacion_id,
        fecha_hora=body.fecha_hora,
    )


@router.get(
    "/api/coloquios/mis-reservas",
    response_model=MisReservasResponse,
)
async def mis_reservas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_alumno),
):
    """List current student's reservations. (AT-11)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    items = await service.listar_mis_reservas()
    return MisReservasResponse(items=items)


@router.delete(
    "/api/coloquios/reservas/{reserva_id}",
    status_code=200,
)
async def cancelar_reserva(
    reserva_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_alumno),
):
    """Cancel a reservation. (AT-09)"""
    service = ColoquioService(
        db=db, tenant_id=current_user.tenant_id, current_user_id=current_user.id,
    )
    result = await service.cancelar_reserva(reserva_id=reserva_id)
    if result:
        return {"detail": "Reserva cancelada exitosamente"}
    raise HTTPException(status_code=404, detail="Reserva no encontrada")
