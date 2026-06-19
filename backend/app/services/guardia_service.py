"""Guardia service — register, list, update, and export guardia records.

Pure functions at the top (testable without DB) followed by service methods.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asignacion import Asignacion
from app.models.guardia import EstadoGuardia, Guardia
from app.models.materia import Materia
from app.models.user import User
from app.repositories.guardia_repository import GuardiaRepository
from app.schemas.guardias import (
    GuardiaCrearRequest,
    GuardiaListResponse,
    GuardiaResponse,
    GuardiaUpdateRequest,
)
from app.services.audit_service import log_action


# ═══════════════════════════════════════════════════════════════════════════════
# Pure functions (testable without DB)
# ═══════════════════════════════════════════════════════════════════════════════


def exportar_csv_guardias(data: list[dict[str, Any]]) -> str:
    """Generate CSV string from guardia export data.

    Args:
        data: List of dicts with dia, horario, estado, materia, carrera,
             cohorte, comentarios, creada_at.

    Returns:
        CSV string with header row.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["dia", "horario", "estado", "materia", "carrera",
                      "cohorte", "comentarios", "creada_at"])
    for row in data:
        creada = row.get("creada_at", "")
        if hasattr(creada, "isoformat"):
            creada = creada.isoformat()
        writer.writerow([
            row.get("dia", ""),
            row.get("horario", ""),
            row.get("estado", ""),
            row.get("materia", ""),
            row.get("carrera", ""),
            row.get("cohorte", ""),
            row.get("comentarios", ""),
            creada,
        ])
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# Service class
# ═══════════════════════════════════════════════════════════════════════════════


class GuardiaService:
    """Service for Guardia operations with scope enforcement."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._repo = GuardiaRepository(session=db, tenant_id=tenant_id)

    async def _get_asignacion_ids(self) -> list[uuid.UUID] | None:
        """Get asignacion_ids for scope-restricted users.

        Returns None for COORDINADOR/ADMIN (full access).
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

    async def _verify_materia_scope(
        self, materia_id: uuid.UUID, asignacion_ids: list[uuid.UUID] | None,
    ) -> None:
        """Verify user has access to materia (raises 403 if not)."""
        if asignacion_ids is None:
            return
        stmt = select(Asignacion.materia_id).where(
            Asignacion.id.in_(asignacion_ids),
            Asignacion.materia_id == materia_id,
            Asignacion.deleted_at.is_(None),
        )
        result = await self._db.execute(stmt)
        if result.fetchone() is None:
            raise HTTPException(
                status_code=403,
                detail="No tienes acceso a esta materia",
            )

    async def crear(self, data: GuardiaCrearRequest) -> GuardiaResponse:
        """Register a new guardia.

        Args:
            data: Validated guardia creation request.

        Returns:
            The created GuardiaResponse.
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

        # Verify scope
        asignacion_ids = await self._get_asignacion_ids()
        if asignacion_ids is not None:
            stmt_asig = select(Asignacion.id).where(
                Asignacion.id.in_(asignacion_ids),
                Asignacion.id == data.asignacion_id,
                Asignacion.deleted_at.is_(None),
            )
            result_asig = await self._db.execute(stmt_asig)
            if result_asig.fetchone() is None:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes acceso a esta asignación",
                )

        guardia = await self._repo.create(
            asignacion_id=data.asignacion_id,
            materia_id=data.materia_id,
            carrera_id=data.carrera_id,
            cohorte_id=data.cohorte_id,
            dia=data.dia,
            horario=data.horario,
            estado=EstadoGuardia.Pendiente.value,
            comentarios=data.comentarios,
        )

        # Audit log
        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="GUARDIA_REGISTRAR",
            detalle={
                "guardia_id": str(guardia.id),
                "materia_id": str(data.materia_id),
            },
            filas_afectadas=1,
            materia_id=data.materia_id,
        )

        return GuardiaResponse.model_validate(guardia)

    async def listar(
        self,
        materia_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        estado: str | None = None,
    ) -> GuardiaListResponse:
        """List guardias with filters and scope enforcement."""
        asignacion_ids = await self._get_asignacion_ids()

        guardias = await self._repo.list_con_filtros(
            materia_id=materia_id,
            estado=estado,
            desde=desde,
            hasta=hasta,
            asignacion_ids=asignacion_ids,
        )

        return GuardiaListResponse(
            items=[GuardiaResponse.model_validate(g) for g in guardias],
            total=len(guardias),
        )

    async def actualizar(
        self, guardia_id: uuid.UUID, data: GuardiaUpdateRequest,
    ) -> GuardiaResponse:
        """Update estado and/or comentarios of a guardia."""
        guardia = await self._repo.get(guardia_id)
        if guardia is None:
            raise HTTPException(
                status_code=404,
                detail="Guardia no encontrada",
            )

        # Verify scope
        asignacion_ids = await self._get_asignacion_ids()
        if asignacion_ids is not None:
            stmt_asig = select(Asignacion.id).where(
                Asignacion.id.in_(asignacion_ids),
                Asignacion.id == guardia.asignacion_id,
                Asignacion.deleted_at.is_(None),
            )
            result_asig = await self._db.execute(stmt_asig)
            if result_asig.fetchone() is None:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes acceso a esta guardia",
                )

        update_kwargs: dict[str, object] = {}
        if data.estado is not None:
            update_kwargs["estado"] = data.estado
        if data.comentarios is not None:
            update_kwargs["comentarios"] = data.comentarios

        if not update_kwargs:
            return GuardiaResponse.model_validate(guardia)

        updated = await self._repo.update(guardia_id, **update_kwargs)
        if updated is None:
            raise HTTPException(status_code=404, detail="Guardia no encontrada")

        # Audit log
        await log_action(
            db=self._db,
            tenant_id=self._tenant_id,
            actor_id=self._current_user.id,
            accion="GUARDIA_EDITAR",
            detalle={
                "guardia_id": str(guardia_id),
                "cambios": update_kwargs,
            },
            filas_afectadas=1,
            materia_id=guardia.materia_id,
        )

        return GuardiaResponse.model_validate(updated)

    async def exportar_csv(
        self,
        materia_id: uuid.UUID | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        estado: str | None = None,
    ) -> str:
        """Export guardias to CSV string."""
        asignacion_ids = await self._get_asignacion_ids()

        guardias = await self._repo.export_query(
            materia_id=materia_id,
            estado=estado,
            desde=desde,
            hasta=hasta,
            asignacion_ids=asignacion_ids,
        )

        # Build export data with materias names
        data_rows: list[dict[str, Any]] = []
        for g in guardias:
            materia_nombre = "N/A"
            if hasattr(g, "materia") and g.materia:
                materia_nombre = g.materia.nombre

            data_rows.append({
                "dia": g.dia,
                "horario": g.horario,
                "estado": g.estado,
                "materia": materia_nombre,
                "carrera": str(g.carrera_id or ""),
                "cohorte": str(g.cohorte_id or ""),
                "comentarios": g.comentarios or "",
                "creada_at": g.creada_at,
            })

        return exportar_csv_guardias(data_rows)
