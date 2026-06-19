"""Aviso repositories — tenant-scoped data access for notices and acknowledgments.

Two repositories:
    - AvisoRepository: CRUD + filtered queries for active notices.
    - AcknowledgmentRepository: immutable audit records for read confirmations.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models.acknowledgment_aviso import AcknowledgmentAviso
from app.models.aviso import Aviso
from app.repositories.base import BaseRepository


class AvisoRepository(BaseRepository[Aviso]):
    """Repository for institutional notices (avisos)."""

    _model_cls = Aviso

    async def list_activos_para_usuario(
        self,
        usuario_id: uuid.UUID,
        roles: list[str],
        materias_ids: list[uuid.UUID],
        cohorte_ids: list[uuid.UUID],
    ) -> Sequence[Aviso]:
        """List active notices visible to a specific user.

        Filters by:
        - activo = True AND NOT soft-deleted
        - Within validity window (inicio_en <= ahora <= fin_en) — RN-18
        - Alcance filtering — RN-20:
            Global: all users
            PorMateria: user must have the materia in materias_ids
            PorCohorte: user must belong to cohorte in cohorte_ids
            PorRol: user must have the role in roles
        - If requiere_ack=True and user already acked → exclude (RN-19)
        - Ordered by orden ASC, tiebreaker created_at DESC
        """
        ahora = datetime.now(UTC)

        # Base conditions
        conditions = [
            Aviso.activo.is_(True),
            Aviso.inicio_en <= ahora,
            Aviso.fin_en >= ahora,
        ]

        # Alcance filtering (OR within alcance — user sees if ANY matches)
        from sqlalchemy import or_
        alcance_conditions = [
            Aviso.alcance == "Global",
        ]
        if roles:
            alcance_conditions.append(
                (Aviso.alcance == "PorRol") & Aviso.rol_destino.in_(roles)
            )
        if cohorte_ids:
            alcance_conditions.append(
                (Aviso.alcance == "PorCohorte") & Aviso.cohorte_id.in_(cohorte_ids)
            )
        if materias_ids:
            alcance_conditions.append(
                (Aviso.alcance == "PorMateria") & Aviso.materia_id.in_(materias_ids)
            )

        conditions.append(or_(*alcance_conditions))

        # Exclude already-acked notices (if requiere_ack)
        ack_subq = (
            select(AcknowledgmentAviso.aviso_id)
            .where(AcknowledgmentAviso.usuario_id == usuario_id)
            .where(AcknowledgmentAviso.tenant_id == self._tenant_id)
            .subquery()
        )
        conditions.append(
            ~Aviso.requiere_ack | ~Aviso.id.in_(select(ack_subq.c.aviso_id))
        )

        stmt = (
            self._exclude_deleted(self._stmt())
            .where(*conditions)
            .order_by(Aviso.orden.asc(), Aviso.created_at.desc())
        )

        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_con_contadores(self) -> list[dict]:
        """List all non-deleted avisos with derived acknowledgment counters.

        Returns a list of dicts with aviso fields plus:
            total_vistos: count of AcknowledgmentAviso records.
            total_acks: same as total_vistos (all acks are "vistos").
        """
        # Subquery: count of acks per aviso
        acks_subq = (
            select(
                AcknowledgmentAviso.aviso_id,
                func.count(AcknowledgmentAviso.id).label("total_acks"),
            )
            .group_by(AcknowledgmentAviso.aviso_id)
            .subquery()
        )

        stmt = (
            self._exclude_deleted(self._stmt())
            .outerjoin(
                acks_subq,
                Aviso.id == acks_subq.c.aviso_id,
            )
            .add_columns(
                func.coalesce(acks_subq.c.total_acks, 0).label("total_acks"),
            )
            .order_by(Aviso.orden.asc(), Aviso.created_at.desc())
        )

        result = await self._session.execute(stmt)
        rows = []
        for row in result.fetchall():
            aviso: Aviso = row[0]
            total_acks = row[1]
            rows.append({
                "id": aviso.id,
                "titulo": aviso.titulo,
                "alcance": aviso.alcance,
                "severidad": aviso.severidad,
                "activo": aviso.activo,
                "inicio_en": aviso.inicio_en,
                "fin_en": aviso.fin_en,
                "orden": aviso.orden,
                "requiere_ack": aviso.requiere_ack,
                "created_at": aviso.created_at,
                "total_vistos": total_acks,
                "total_acks": total_acks,
            })
        return rows


class AcknowledgmentRepository(BaseRepository[AcknowledgmentAviso]):
    """Repository for read acknowledgment records (immutable).

    This repository works with AcknowledgmentAviso which does NOT
    have SoftDeleteMixin — records are append-only.
    """

    _model_cls = AcknowledgmentAviso

    async def create(
        self,
        aviso_id: uuid.UUID,
        usuario_id: uuid.UUID,
        **kwargs: object,
    ) -> AcknowledgmentAviso:
        """Create a new acknowledgment record."""
        import uuid as _uuid
        instance = AcknowledgmentAviso(
            id=_uuid.uuid4(),
            tenant_id=self._tenant_id,
            aviso_id=aviso_id,
            usuario_id=usuario_id,
            confirmado_at=kwargs.get("confirmado_at", datetime.now(UTC)),
        )
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def count_por_aviso(self, aviso_id: uuid.UUID) -> int:
        """Count acknowledgments for a specific notice."""
        stmt = (
            select(func.count(AcknowledgmentAviso.id))
            .where(AcknowledgmentAviso.aviso_id == aviso_id)
            .where(AcknowledgmentAviso.tenant_id == self._tenant_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def list_por_aviso(
        self, aviso_id: uuid.UUID,
    ) -> Sequence[AcknowledgmentAviso]:
        """List all acknowledgments for a specific notice."""
        stmt = (
            select(AcknowledgmentAviso)
            .where(AcknowledgmentAviso.aviso_id == aviso_id)
            .where(AcknowledgmentAviso.tenant_id == self._tenant_id)
            .order_by(AcknowledgmentAviso.confirmado_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def exists_por_usuario(
        self, aviso_id: uuid.UUID, usuario_id: uuid.UUID,
    ) -> bool:
        """Check if a user has already acknowledged a notice."""
        stmt = (
            select(AcknowledgmentAviso.id)
            .where(AcknowledgmentAviso.aviso_id == aviso_id)
            .where(AcknowledgmentAviso.usuario_id == usuario_id)
            .where(AcknowledgmentAviso.tenant_id == self._tenant_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
