"""Encuentro service — creates slots with instance generation, instance editing,
HTML block generation, and scope enforcement.

Pure functions at the top (testable without DB) followed by service methods.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from html import escape
from typing import Any, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asignacion import Asignacion
from app.models.instancia_encuentro import EstadoInstancia, InstanciaEncuentro
from app.models.materia import Materia
from app.models.slot_encuentro import SlotEncuentro
from app.models.user import User
from app.repositories.encuentro_repository import (
    InstanciaEncuentroRepository,
    SlotEncuentroRepository,
)
from app.schemas.encuentros import (
    HtmlResponse,
    InstanciaListResponse,
    InstanciaResponse,
    InstanciaUpdateRequest,
    SlotConInstanciasResponse,
    SlotCrearRequest,
    SlotListResponse,
    SlotResponse,
)
from app.services.audit_service import log_action


# ═══════════════════════════════════════════════════════════════════════════════
# Pure functions (testable without DB)
# ═══════════════════════════════════════════════════════════════════════════════


def _generar_fechas_instancias(
    fecha_inicio: date,
    cant_semanas: int,
    fecha_unica: date | None,
    titulo: str,
    hora: str,
) -> list[dict[str, Any]]:
    """Generate instance date data from a slot definition.

    Args:
        fecha_inicio: Start date for weekly iteration.
        cant_semanas: Number of instances (0 = single date mode).
        fecha_unica: Specific date for single-instance mode.
        titulo: Base title (enumerated as "titulo #N" for recurrent).
        hora: Time string for each instance.

    Returns:
        List of dicts with fecha, hora, titulo keys.

    Raises:
        ValueError: If the mode is invalid (both/neither).
    """
    if cant_semanas == 0 and fecha_unica is None:
        raise ValueError("Modo inválido: debe especificar cant_semanas > 0 o fecha_unica")
    if cant_semanas > 0 and fecha_unica is not None:
        # Both set — prefer recurrent (should have been caught by schema)
        pass

    result: list[dict[str, Any]] = []

    if cant_semanas > 0:
        for i in range(cant_semanas):
            fecha = fecha_inicio + timedelta(weeks=i)
            result.append({
                "fecha": fecha,
                "hora": hora,
                "titulo": f"{titulo} #{i + 1}",
            })
    else:
        result.append({
            "fecha": fecha_unica,
            "hora": hora,
            "titulo": titulo,
        })

    return result


def _format_fecha(fecha: date) -> str:
    """Format date in DD/MM format for HTML display."""
    return fecha.strftime("%d/%m")


def generar_html_instancias(
    materia_nombre: str,
    instancias: Sequence[Any],
) -> str:
    """Generate an HTML block with encuentro instances.

    Args:
        materia_nombre: Display name of the materia.
        instancias: Sequence of objects with fecha, hora, titulo, estado,
                   meet_url, video_url attributes.

    Returns:
        HTML string with encuentro listing, safe for embedding.
    """
    parts: list[str] = []
    parts.append(f'<div class="encuentros-semana">')
    parts.append(f'  <h3>Encuentros de {escape(materia_nombre)}</h3>')
    parts.append(f'  <ul>')

    for inst in instancias:
        fecha_str = _format_fecha(inst.fecha)
        meet_html = ""
        if inst.meet_url:
            safe_url = escape(inst.meet_url)
            meet_html = f' <a href="{safe_url}">Enlace</a>'
        video_html = ""
        if inst.video_url:
            safe_url = escape(inst.video_url)
            video_html = f' <a href="{safe_url}">Grabación</a>'
        estado_label = f"[{inst.estado}]" if inst.estado != "Programado" else ""

        parts.append(
            f'    <li><strong>{_format_fecha(inst.fecha)}</strong>'
            f' - {escape(inst.hora)} hs - {escape(inst.titulo)}'
            f' {estado_label}{meet_html}{video_html}</li>'
        )

    parts.append('  </ul>')
    parts.append('</div>')
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Service class
# ═══════════════════════════════════════════════════════════════════════════════


class EncuentroService:
    """Service for Encuentro operations with scope enforcement."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._slot_repo = SlotEncuentroRepository(session=db, tenant_id=tenant_id)
        self._inst_repo = InstanciaEncuentroRepository(session=db, tenant_id=tenant_id)

    async def _get_asignacion_ids(self) -> list[uuid.UUID] | None:
        """Get asignacion_ids for scope-restricted users.

        Returns None for COORDINADOR/ADMIN (full access).
        Returns list of asignacion_ids for PROFESOR/TUTOR/NEXO.
        """
        from app.models.rbac import UserRole as UserRoleModel
        from sqlalchemy.orm import joinedload

        role_stmt = select(UserRoleModel).where(
            UserRoleModel.user_id == self._current_user.id,
            UserRoleModel.tenant_id == self._tenant_id,
            UserRoleModel.deleted_at.is_(None),
        ).options(joinedload(UserRoleModel.role))
        role_result = await self._db.execute(role_stmt)
        role_codes = {ur.role.codigo for ur in role_result.scalars().all()}

        is_restricted = (
            "COORDINADOR" not in role_codes
            and "ADMIN" not in role_codes
        )

        if not is_restricted:
            return None

        stmt = select(Asignacion.id).where(
            Asignacion.tenant_id == self._tenant_id,
            Asignacion.usuario_id == self._current_user.id,
            Asignacion.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def _get_materia_ids_from_asignaciones(
        self, asignacion_ids: list[uuid.UUID] | None,
    ) -> list[uuid.UUID] | None:
        """Resolve materia_ids from asignacion_ids."""
        if asignacion_ids is None:
            return None
        stmt = select(Asignacion.materia_id).where(
            Asignacion.id.in_(asignacion_ids),
            Asignacion.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        return list({row[0] for row in result.fetchall() if row[0] is not None})

    async def _verify_materia_scope(
        self, materia_id: uuid.UUID, asignacion_ids: list[uuid.UUID] | None,
    ) -> None:
        """Verify user has access to materia (raises 403 if not)."""
        if asignacion_ids is None:
            return  # Full access
        materia_ids = await self._get_materia_ids_from_asignaciones(asignacion_ids)
        if materia_ids is None or materia_id not in materia_ids:
            raise HTTPException(
                status_code=403,
                detail="No tienes acceso a esta materia",
            )

    async def crear_slot(self, data: SlotCrearRequest) -> SlotConInstanciasResponse:
        """Create a slot and generate its instances synchronously.

        Args:
            data: Validated slot creation request.

        Returns:
            SlotConInstanciasResponse with slot + generated instances.
        """
        # Verify materia exists
        stmt = select(Materia).where(
            Materia.id == data.materia_id,
            Materia.tenant_id == self._tenant_id,
            Materia.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=404,
                detail="Materia no encontrada en el tenant",
            )

        # Get user's asignacion for this materia
        asignacion_ids = await self._get_asignacion_ids()
        if asignacion_ids is not None:
            # Get the asignacion_id for this materia
            stmt_asig = select(Asignacion.id).where(
                Asignacion.id.in_(asignacion_ids),
                Asignacion.materia_id == data.materia_id,
                Asignacion.deleted_at.is_(None),
            )
            result_asig = await self._db.execute(stmt_asig)
            row = result_asig.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes acceso a esta materia",
                )
            asignacion_id = row[0]
        else:
            # Full access — pick any asignacion for the materia
            stmt_asig = select(Asignacion.id).where(
                Asignacion.materia_id == data.materia_id,
                Asignacion.tenant_id == self._tenant_id,
                Asignacion.deleted_at.is_(None),
            ).limit(1)
            result_asig = await self._db.execute(stmt_asig)
            row = result_asig.fetchone()
            if row is None:
                raise HTTPException(
                    status_code=400,
                    detail="No hay asignación para esta materia",
                )
            asignacion_id = row[0]

        # Create the slot
        slot = await self._slot_repo.create(
            asignacion_id=asignacion_id,
            materia_id=data.materia_id,
            titulo=data.titulo,
            hora=data.hora,
            dia_semana=data.dia_semana,
            fecha_inicio=data.fecha_inicio,
            cant_semanas=data.cant_semanas,
            fecha_unica=data.fecha_unica,
            meet_url=data.meet_url,
        )

        # Generate instance dates
        fechas_data = _generar_fechas_instancias(
            fecha_inicio=data.fecha_inicio,
            cant_semanas=data.cant_semanas,
            fecha_unica=data.fecha_unica,
            titulo=data.titulo,
            hora=data.hora,
        )

        # Create instances
        instancias: list[InstanciaEncuentro] = []
        for fd in fechas_data:
            inst = InstanciaEncuentro(
                tenant_id=self._tenant_id,
                slot_id=slot.id,
                materia_id=data.materia_id,
                fecha=fd["fecha"],
                hora=fd["hora"],
                titulo=fd["titulo"],
                estado=EstadoInstancia.Programado.value,
                meet_url=data.meet_url,
            )
            self._db.add(inst)
            instancias.append(inst)

        await self._db.flush()

        # Refresh instances to get IDs
        for inst in instancias:
            await self._db.refresh(inst)

        # Audit log
        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="ENCUENTRO_CREAR",
            detalle={
                "slot_id": str(slot.id),
                "materia_id": str(data.materia_id),
                "total_instancias": len(instancias),
                "modo": "recurrente" if data.cant_semanas > 0 else "fecha_unica",
            },
            filas_afectadas=len(instancias) + 1,
            materia_id=data.materia_id,
        )

        return SlotConInstanciasResponse(
            slot=SlotResponse.model_validate(slot),
            instancias=[InstanciaResponse.model_validate(i) for i in instancias],
            total_instancias=len(instancias),
        )

    async def editar_instancia(
        self, instancia_id: uuid.UUID, data: InstanciaUpdateRequest,
    ) -> InstanciaResponse:
        """Update estado and optional fields of an instance.

        Any state → any state (RN-14).
        """
        instance = await self._inst_repo.get(instancia_id)
        if instance is None:
            raise HTTPException(
                status_code=404,
                detail="Instancia no encontrada",
            )

        # Verify scope
        asignacion_ids = await self._get_asignacion_ids()
        await self._verify_materia_scope(instance.materia_id, asignacion_ids)

        # Build update kwargs (only non-None fields)
        update_kwargs: dict[str, object] = {}
        if data.estado is not None:
            update_kwargs["estado"] = data.estado
        if data.meet_url is not None:
            update_kwargs["meet_url"] = data.meet_url
        if data.video_url is not None:
            update_kwargs["video_url"] = data.video_url
        if data.comentario is not None:
            update_kwargs["comentario"] = data.comentario

        # Apply update
        if update_kwargs:
            estado = str(update_kwargs.get("estado", instance.estado))
            extra = {k: v for k, v in update_kwargs.items() if k != "estado"}
            updated = await self._inst_repo.update_estado(
                id=instancia_id, estado=estado, **extra,
            )
            if updated is None:
                raise HTTPException(status_code=404, detail="Instancia no encontrada")
            instance = updated

        # Audit
        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="INSTANCIA_EDITAR",
            detalle={
                "instancia_id": str(instancia_id),
                "cambios": update_kwargs,
            },
            filas_afectadas=1,
            materia_id=instance.materia_id,
        )

        return InstanciaResponse.model_validate(instance)

    async def listar_instancias(
        self,
        materia_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> InstanciaListResponse:
        """List instances with optional filters and scope enforcement."""
        asignacion_ids = await self._get_asignacion_ids()
        materia_ids = await self._get_materia_ids_from_asignaciones(asignacion_ids)

        # If restricted user and no specific materia, scope to their materias
        if materia_id is not None:
            if materia_ids is not None and materia_id not in materia_ids:
                return InstanciaListResponse(items=[], total=0)
            instances = await self._inst_repo.list_por_materia_fechas(
                materia_id=materia_id, desde=desde, hasta=hasta,
            )
        elif materia_ids is not None:
            # List across all their materias
            all_instances: list[InstanciaEncuentro] = []
            for mid in materia_ids:
                insts = await self._inst_repo.list_por_materia_fechas(
                    materia_id=mid, desde=desde, hasta=hasta,
                )
                all_instances.extend(insts)
            all_instances.sort(key=lambda x: x.fecha)
            instances = all_instances
        else:
            instances = await self._inst_repo.list_por_materia_fechas(
                materia_id=None, desde=desde, hasta=hasta,
            )

        return InstanciaListResponse(
            items=[InstanciaResponse.model_validate(i) for i in instances],
            total=len(instances),
        )

    async def listar_slots(
        self, materia_id: uuid.UUID | None = None,
    ) -> SlotListResponse:
        """List slots with scope enforcement."""
        asignacion_ids = await self._get_asignacion_ids()
        materia_ids = await self._get_materia_ids_from_asignaciones(asignacion_ids)

        if materia_id is not None:
            if materia_ids is not None and materia_id not in materia_ids:
                return SlotListResponse(items=[], total=0)
            slots = await self._slot_repo.list_por_materia(materia_id)
        elif materia_ids is not None:
            all_slots: list[SlotEncuentro] = []
            for mid in materia_ids:
                sl = await self._slot_repo.list_por_materia(mid)
                all_slots.extend(sl)
            slots = all_slots
        else:
            slots = await self._slot_repo.list()

        return SlotListResponse(
            items=[SlotResponse.model_validate(s) for s in slots],
            total=len(slots),
        )

    async def generar_html(
        self, instancia_id: uuid.UUID,
    ) -> HtmlResponse:
        """Generate HTML block for a single instance's context."""
        instance = await self._inst_repo.get(instancia_id)
        if instance is None:
            raise HTTPException(
                status_code=404,
                detail="Instancia no encontrada",
            )

        asignacion_ids = await self._get_asignacion_ids()
        await self._verify_materia_scope(instance.materia_id, asignacion_ids)

        # Get materia name
        stmt = select(Materia.nombre).where(
            Materia.id == instance.materia_id,
            Materia.tenant_id == self._tenant_id,
        )
        result = await self._db.execute(stmt)
        materia_nombre = result.scalar_one_or_none() or "Materia"

        # Get all instances for the same materia (for context)
        instancias = await self._inst_repo.list_por_materia_fechas(
            materia_id=instance.materia_id,
        )

        html = generar_html_instancias(materia_nombre, instancias)
        return HtmlResponse(html=html)

    async def vista_admin(
        self,
        materia_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        estado: str | None = None,
    ) -> InstanciaListResponse:
        """Admin view — all instances across the tenant.

        Only for COORDINADOR/ADMIN roles.
        """
        asignacion_ids = await self._get_asignacion_ids()
        if asignacion_ids is not None:
            # Not admin/coord — use regular listing
            return await self.listar_instancias(
                materia_id=materia_id, desde=desde, hasta=hasta,
            )

        instances = await self._inst_repo.list_por_materia_fechas(
            materia_id=materia_id, desde=desde, hasta=hasta,
        )

        if estado:
            instances = [i for i in instances if i.estado == estado]

        return InstanciaListResponse(
            items=[InstanciaResponse.model_validate(i) for i in instances],
            total=len(instances),
        )
