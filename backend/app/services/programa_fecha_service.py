"""Programa/Fecha service — CRUD for syllabus and evaluation dates."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.programa_repository import ProgramaRepository
from app.repositories.fecha_repository import FechaRepository
from app.schemas.programas_fechas import (
    ProgramaCrearRequest, ProgramaUpdateRequest, ProgramaResponse, ProgramaListResponse,
    FechaCrearRequest, FechaUpdateRequest, FechaResponse, FechaListResponse,
)
from app.services.audit_service import log_action


class ProgramaFechaService:
    """Service for syllabus programs and academic evaluation dates."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, current_user: User):
        self._db = db
        self._tenant_id = tenant_id
        self._current_user = current_user
        self._programa_repo = ProgramaRepository(session=db, tenant_id=tenant_id)
        self._fecha_repo = FechaRepository(session=db, tenant_id=tenant_id)

    # ── Programas ──────────────────────────────────────────────────────────

    async def crear_programa(self, data: ProgramaCrearRequest) -> ProgramaResponse:
        p = await self._programa_repo.create(
            materia_id=data.materia_id, carrera_id=data.carrera_id,
            cohorte_id=data.cohorte_id, titulo=data.titulo,
            referencia_archivo=data.referencia_archivo,
        )
        await self._db.flush()
        await log_action(self._db, self._tenant_id, self._current_user.id,
                         "PROGRAMA_CREAR", detalle={"programa_id": str(p.id)})
        return self._to_programa_response(p)

    async def listar_programas(
        self, materia_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
    ) -> ProgramaListResponse:
        progs = await self._programa_repo.list_con_filtros(
            tenant_id=self._tenant_id, materia_id=materia_id, cohorte_id=cohorte_id,
        )
        return ProgramaListResponse(
            items=[self._to_programa_response(p) for p in progs],
            total=len(progs),
        )

    async def actualizar_programa(
        self, programa_id: uuid.UUID, data: ProgramaUpdateRequest,
    ) -> ProgramaResponse:
        p = await self._programa_repo.get(programa_id)
        if p is None:
            raise HTTPException(status_code=404, detail="Programa no encontrado")
        updates: dict = {}
        if data.titulo is not None:
            updates["titulo"] = data.titulo
        if data.referencia_archivo is not None:
            updates["referencia_archivo"] = data.referencia_archivo
        if updates:
            await self._programa_repo.update(programa_id, **updates)
        return self._to_programa_response(p)

    async def eliminar_programa(self, programa_id: uuid.UUID) -> None:
        p = await self._programa_repo.get(programa_id)
        if p is None:
            raise HTTPException(status_code=404, detail="Programa no encontrado")
        await self._programa_repo.soft_delete(programa_id)
        await log_action(self._db, self._tenant_id, self._current_user.id,
                         "PROGRAMA_ELIMINAR", detalle={"programa_id": str(programa_id)})

    # ── Fechas ─────────────────────────────────────────────────────────────

    async def crear_fecha(self, data: FechaCrearRequest) -> FechaResponse:
        f = await self._fecha_repo.create(
            materia_id=data.materia_id, cohorte_id=data.cohorte_id,
            tipo=data.tipo, numero=data.numero, periodo=data.periodo,
            fecha=data.fecha, titulo=data.titulo,
        )
        await self._db.flush()
        await log_action(self._db, self._tenant_id, self._current_user.id,
                         "FECHA_CREAR", detalle={"fecha_id": str(f.id)})
        return self._to_fecha_response(f)

    async def listar_fechas(
        self, materia_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
        tipo: str | None = None, periodo: str | None = None,
    ) -> FechaListResponse:
        fechas = await self._fecha_repo.list_con_filtros(
            tenant_id=self._tenant_id, materia_id=materia_id,
            cohorte_id=cohorte_id, tipo=tipo, periodo=periodo,
        )
        return FechaListResponse(
            items=[self._to_fecha_response(f) for f in fechas],
            total=len(fechas),
        )

    async def actualizar_fecha(
        self, fecha_id: uuid.UUID, data: FechaUpdateRequest,
    ) -> FechaResponse:
        f = await self._fecha_repo.get(fecha_id)
        if f is None:
            raise HTTPException(status_code=404, detail="Fecha no encontrada")
        updates: dict = {}
        for field in ("tipo", "numero", "periodo", "fecha", "titulo"):
            val = getattr(data, field)
            if val is not None:
                updates[field] = val
        if updates:
            await self._fecha_repo.update(fecha_id, **updates)
        return self._to_fecha_response(f)

    async def eliminar_fecha(self, fecha_id: uuid.UUID) -> None:
        f = await self._fecha_repo.get(fecha_id)
        if f is None:
            raise HTTPException(status_code=404, detail="Fecha no encontrada")
        await self._fecha_repo.soft_delete(fecha_id)
        await log_action(self._db, self._tenant_id, self._current_user.id,
                         "FECHA_ELIMINAR", detalle={"fecha_id": str(fecha_id)})

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _to_programa_response(self, p) -> ProgramaResponse:
        return ProgramaResponse(
            id=p.id, materia_id=p.materia_id, carrera_id=p.carrera_id,
            cohorte_id=p.cohorte_id, titulo=p.titulo,
            referencia_archivo=p.referencia_archivo,
            cargado_at=getattr(p, "cargado_at", None),
            created_at=p.created_at,
        )

    def _to_fecha_response(self, f) -> FechaResponse:
        return FechaResponse(
            id=f.id, materia_id=f.materia_id, cohorte_id=f.cohorte_id,
            tipo=f.tipo, numero=f.numero, periodo=f.periodo,
            fecha=f.fecha, titulo=f.titulo, created_at=f.created_at,
        )
