"""Equipos router — high-level team management operations.

Endpoints:
- GET  /api/equipos/mi-equipo         — docente views their assignments
- GET  /api/equipos                   — gestionar all tenant assignments
- POST /api/equipos/asignacion-masiva — bulk create assignments
- POST /api/equipos/clonar            — clone equipo between cohorts
- PATCH /api/equipos/vigencia         — bulk update vigencia dates
- GET  /api/equipos/exportar          — CSV export
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.asignacion_repository import AsignacionRepository
from app.schemas.asignacion import AsignacionDocenteInfo
from app.schemas.equipo import (
    AsignacionMasivaRequest,
    AsignacionMasivaResponse,
    CloneEquipoRequest,
    CloneEquipoResponse,
    EquipoListResponse,
    VigenciaRequest,
    VigenciaResponse,
)

router = APIRouter(tags=["equipos"])


def _to_docente_info(a) -> AsignacionDocenteInfo:
    """Build AsignacionDocenteInfo from an Asignacion ORM instance.

    The ORM model has relationships loaded via joinedload or manual query.
    We manually construct the nested objects since Pydantic's from_attributes
    may not handle the nested ORM relationships automatically.
    """
    from app.schemas.asignacion import (
        CarreraInfo,
        CohorteInfo,
        MateriaInfo,
        ResponsableInfo,
        UsuarioInfo,
    )

    usuario = UsuarioInfo.model_validate(a.usuario) if a.usuario else None
    materia = MateriaInfo.model_validate(a.materia) if a.materia else None
    carrera = CarreraInfo.model_validate(a.carrera) if a.carrera else None
    cohorte = CohorteInfo.model_validate(a.cohorte) if a.cohorte else None
    responsable = ResponsableInfo.model_validate(a.responsable) if a.responsable else None

    return AsignacionDocenteInfo(
        id=a.id,
        usuario=usuario,
        materia=materia,
        carrera=carrera,
        cohorte=cohorte,
        comisiones=a.comisiones,
        rol=a.rol,
        desde=a.desde,
        hasta=a.hasta,
        responsable=responsable,
        estado_vigencia=a.estado_vigencia,
    )


async def _log_audit(
    db: AsyncSession,
    current_user: User,
    accion: str,
    detalle: dict,
    filas_afectadas: int = 1,
) -> None:
    """Create an audit log entry."""
    log = AuditLog(
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        accion=accion,
        detalle=detalle,
        filas_afectadas=filas_afectadas,
    )
    db.add(log)


# ── E1: Docente ve su equipo ──────────────────────────────────────────────


@router.get(
    "/mi-equipo",
    response_model=EquipoListResponse,
)
async def mi_equipo(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return vigentes assignments for the authenticated user.

    Accessible to any authenticated user (no special permission).
    """
    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    asignaciones, total = await repo.list_equipo_docente(
        usuario_id=current_user.id,
    )
    items = [_to_docente_info(a) for a in asignaciones]
    return EquipoListResponse(items=items, total=total)


# ── E2: COORDINADOR gestiona equipos del tenant ───────────────────────────


@router.get(
    "",
    response_model=EquipoListResponse,
    dependencies=[Depends(require_permission("equipos:gestionar"))],
)
async def list_equipos(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    materia_id: uuid.UUID | None = Query(default=None),
    carrera_id: uuid.UUID | None = Query(default=None),
    cohorte_id: uuid.UUID | None = Query(default=None),
    rol: str | None = Query(default=None),
    docente_id: uuid.UUID | None = Query(default=None),
    vigentes_only: bool = Query(default=True),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tenant assignments with filters, pagination, and text search.

    Requires equipos:gestionar permission.
    """
    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    asignaciones, total = await repo.list_equipos_tenant(
        skip=skip,
        limit=limit,
        materia_id=materia_id,
        carrera_id=carrera_id,
        cohorte_id=cohorte_id,
        rol=rol,
        docente_id=docente_id,
        vigentes_only=vigentes_only,
        q=q,
    )
    items = [_to_docente_info(a) for a in asignaciones]
    return EquipoListResponse(items=items, total=total)


# ── E3: Asignación masiva ─────────────────────────────────────────────────


@router.post(
    "/asignacion-masiva",
    response_model=AsignacionMasivaResponse,
    status_code=201,
    dependencies=[Depends(require_permission("equipos:gestionar"))],
)
async def asignacion_masiva(
    body: AsignacionMasivaRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk create assignments within a single academic context.

    All assignments share the same materia, carrera, cohorte, comisiones,
    and vigencia dates. Max 200 per request.
    """
    if len(body.asignaciones) > 200:
        raise HTTPException(
            status_code=400,
            detail="Maximo 200 asignaciones por operacion",
        )

    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    items_data = [
        {
            "usuario_id": item.usuario_id,
            "rol": item.rol,
            "materia_id": body.materia_id,
            "carrera_id": body.carrera_id,
            "cohorte_id": body.cohorte_id,
            "comisiones": body.comisiones,
            "responsable_id": item.responsable_id,
            "desde": body.desde,
            "hasta": body.hasta,
        }
        for item in body.asignaciones
    ]

    created = await repo.bulk_create(items_data)

    # Audit log
    await _log_audit(
        db=db,
        current_user=current_user,
        accion="ASIGNACION_MODIFICAR",
        detalle={
            "operacion": "bulk_create",
            "cantidad": len(created),
            "materia_id": str(body.materia_id),
            "carrera_id": str(body.carrera_id),
            "cohorte_id": str(body.cohorte_id),
        },
        filas_afectadas=len(created),
    )

    items = [_to_docente_info(a) for a in created]
    return AsignacionMasivaResponse(creadas=len(created), items=items)


# ── E4: Clonar equipo entre cohortes ──────────────────────────────────────


@router.post(
    "/clonar",
    response_model=CloneEquipoResponse,
    status_code=201,
    dependencies=[Depends(require_permission("equipos:gestionar"))],
)
async def clonar_equipo(
    body: CloneEquipoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone vigentes assignments from origin to destination context.

    Dates are taken from cohorte_destino.vig_desde/vig_hasta.
    Duplicates are skipped per RN-12.
    """
    origen = body.origen
    destino = body.destino

    # Validate origen != destino
    if (origen.materia_id == destino.materia_id
            and origen.carrera_id == destino.carrera_id
            and origen.cohorte_id == destino.cohorte_id):
        raise HTTPException(
            status_code=400,
            detail="Origen y destino no pueden ser iguales",
        )

    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    nuevas_ids = await repo.clone_equipo(
        origen_materia_id=origen.materia_id,
        origen_carrera_id=origen.carrera_id,
        origen_cohorte_id=origen.cohorte_id,
        destino_materia_id=destino.materia_id,
        destino_carrera_id=destino.carrera_id,
        destino_cohorte_id=destino.cohorte_id,
        incluir_roles=body.incluir_roles,
    )

    # Audit log
    await _log_audit(
        db=db,
        current_user=current_user,
        accion="ASIGNACION_MODIFICAR",
        detalle={
            "operacion": "clone",
            "cantidad": len(nuevas_ids),
            "origen": {
                "materia_id": str(origen.materia_id),
                "carrera_id": str(origen.carrera_id),
                "cohorte_id": str(origen.cohorte_id),
            },
            "destino": {
                "materia_id": str(destino.materia_id),
                "carrera_id": str(destino.carrera_id),
                "cohorte_id": str(destino.cohorte_id),
            },
        },
        filas_afectadas=len(nuevas_ids),
    )

    return CloneEquipoResponse(clonadas=len(nuevas_ids), items=nuevas_ids)


# ── E5: Modificar vigencia en bloque ─────────────────────────────────────


@router.patch(
    "/vigencia",
    response_model=VigenciaResponse,
    dependencies=[Depends(require_permission("equipos:gestionar"))],
)
async def update_vigencia(
    body: VigenciaRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk update vigencia (desde/hasta) for matching assignments.

    Requires confirmar=true for full-tenant updates or past dates.
    """
    if body.nuevo_desde is None and body.nuevo_hasta is None:
        raise HTTPException(
            status_code=400,
            detail="Debe especificar al menos nuevo_desde o nuevo_hasta",
        )

    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    updated_ids = await repo.update_vigencia_masiva(
        materia_id=body.materia_id,
        carrera_id=body.carrera_id,
        cohorte_id=body.cohorte_id,
        rol=body.rol,
        nuevo_desde=body.nuevo_desde,
        nuevo_hasta=body.nuevo_hasta,
        confirmar=body.confirmar,
    )

    # Audit log
    await _log_audit(
        db=db,
        current_user=current_user,
        accion="ASIGNACION_MODIFICAR",
        detalle={
            "operacion": "vigencia_update",
            "cantidad": len(updated_ids),
            "filtros": {
                "materia_id": str(body.materia_id) if body.materia_id else None,
                "carrera_id": str(body.carrera_id) if body.carrera_id else None,
                "cohorte_id": str(body.cohorte_id) if body.cohorte_id else None,
                "rol": body.rol,
            },
        },
        filas_afectadas=len(updated_ids),
    )

    return VigenciaResponse(actualizadas=len(updated_ids), items=updated_ids)


# ── E6: Exportar equipo a CSV ─────────────────────────────────────────────


@router.get(
    "/exportar",
    dependencies=[Depends(require_permission("equipos:gestionar"))],
)
async def exportar_equipo(
    materia_id: uuid.UUID | None = Query(default=None),
    carrera_id: uuid.UUID | None = Query(default=None),
    cohorte_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export team assignments to CSV (utf-8-sig BOM).

    Max 10,000 rows. Columns: id, docente_nombre, docente_email, materia,
    carrera, cohorte, comisiones, rol, responsable, desde, hasta, estado.
    """
    repo = AsignacionRepository(session=db, tenant_id=current_user.tenant_id)
    asignaciones, _ = await repo.list_equipos_tenant(
        skip=0,
        limit=10000,
        materia_id=materia_id,
        carrera_id=carrera_id,
        cohorte_id=cohorte_id,
        vigentes_only=False,
        q=None,
    )

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "docente_nombre", "docente_email", "materia",
        "carrera", "cohorte", "comisiones", "rol", "responsable",
        "desde", "hasta", "estado",
    ])

    for a in asignaciones:
        usuario_nombre = a.usuario.display_name if a.usuario else ""
        usuario_email = a.usuario.email if a.usuario else ""
        materia_nombre = a.materia.nombre if hasattr(a, "materia") and a.materia else ""
        carrera_nombre = a.carrera.nombre if hasattr(a, "carrera") and a.carrera else ""
        cohorte_nombre = a.cohorte.nombre if hasattr(a, "cohorte") and a.cohorte else ""
        responsable_nombre = a.responsable.display_name if a.responsable else ""

        writer.writerow([
            str(a.id),
            usuario_nombre,
            usuario_email,
            materia_nombre,
            carrera_nombre,
            cohorte_nombre,
            ",".join(a.comisiones) if a.comisiones else "",
            a.rol,
            responsable_nombre,
            a.desde.isoformat(),
            a.hasta.isoformat() if a.hasta else "",
            a.estado_vigencia,
        ])

    csv_content = output.getvalue()
    output.close()

    # Audit log
    await _log_audit(
        db=db,
        current_user=current_user,
        accion="ASIGNACION_MODIFICAR",
        detalle={
            "operacion": "export",
            "cantidad": len(asignaciones),
            "filtros": {
                "materia_id": str(materia_id) if materia_id else None,
                "carrera_id": str(carrera_id) if carrera_id else None,
                "cohorte_id": str(cohorte_id) if cohorte_id else None,
            },
        },
        filas_afectadas=len(asignaciones),
    )

    filename = f"equipo_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
