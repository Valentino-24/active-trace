"""Asignacion repository — tenant-scoped data access for assignments."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import or_, select, func
from sqlalchemy.orm import joinedload

from app.models.asignacion import Asignacion
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.user import User
from app.repositories.base import BaseRepository


class AsignacionRepository(BaseRepository[Asignacion]):
    """Repository for Asignacion entities with tenant scoping."""

    _model_cls = Asignacion

    async def list_asignaciones(
        self,
        skip: int = 0,
        limit: int = 100,
        usuario_id: uuid.UUID | None = None,
        materia_id: uuid.UUID | None = None,
        rol: str | None = None,
        incluir_vencidas: bool = False,
    ) -> tuple[list[Asignacion], int]:
        """List asignaciones with optional filters and pagination.

        By default returns only vigentes (not vencidas) unless
        incluir_vencidas=True.

        Args:
            skip: Number of records to skip.
            limit: Max records to return.
            usuario_id: Filter by assigned user.
            materia_id: Filter by materia.
            rol: Filter by role code.
            incluir_vencidas: Include expired assignments.

        Returns:
            Tuple of (asignaciones list, total count).
        """
        stmt = self._exclude_deleted(self._stmt())

        if usuario_id is not None:
            stmt = stmt.where(Asignacion.usuario_id == usuario_id)
        if materia_id is not None:
            stmt = stmt.where(Asignacion.materia_id == materia_id)
        if rol is not None:
            stmt = stmt.where(Asignacion.rol == rol)

        today = datetime.now(UTC).date()
        if not incluir_vencidas:
            stmt = stmt.where(
                (Asignacion.hasta.is_(None)) | (Asignacion.hasta >= today)
            )

        # Count
        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        # Paginate
        stmt = stmt.offset(skip).limit(limit).order_by(Asignacion.desde.desc())
        result = await self._session.execute(stmt)
        asignaciones = list(result.scalars().all())

        return asignaciones, total

    async def revoke(self, asignacion_id: uuid.UUID) -> Asignacion | None:
        """Revoke an asignacion by setting hasta = today.

        Idempotent: if already vencida, returns the current state.

        Args:
            asignacion_id: UUID of the asignacion to revoke.

        Returns:
            Updated Asignacion or None if not found.
        """
        asignacion = await self.get(asignacion_id)
        if asignacion is None:
            return None

        today = datetime.now(UTC).date()
        if asignacion.hasta is None or asignacion.hasta > today:
            asignacion.hasta = today
            await self._session.flush()
            await self._session.refresh(asignacion)

        return asignacion

    # ── Bulk operations (C-08 equipos-docentes) ─────────────────────────

    async def bulk_create(
        self,
        items: list[dict],
    ) -> list[Asignacion]:
        """Create multiple asignaciones in a single transaction.

        Validates that all usuario_ids exist in the tenant beforehand.

        Args:
            items: List of dicts with Asignacion field values.
                   Must include tenant_id in each dict or rely on
                   the repository's tenant_id.

        Returns:
            List of created Asignacion instances.
        """
        # Validate all usuario_ids exist in this tenant
        usuario_ids = {item["usuario_id"] for item in items if "usuario_id" in item}
        if usuario_ids:
            stmt = select(User).where(
                User.tenant_id == self._tenant_id,
                User.id.in_(usuario_ids),
                User.deleted_at.is_(None),
            )
            result = await self._session.execute(stmt)
            existing_ids = {u.id for u in result.scalars().all()}
            missing = usuario_ids - existing_ids
            if missing:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=400,
                    detail=f"Usuarios no encontrados en el tenant: {[str(m) for m in missing]}",
                )

        created: list[Asignacion] = []
        for item in items:
            instance = self._model_cls(**item, tenant_id=self._tenant_id)
            self._session.add(instance)
            created.append(instance)

        await self._session.flush()

        # Eager-load usuario and responsable relationships for each created instance
        for instance in created:
            await self._session.refresh(instance, ["usuario", "responsable"])
            # Manually load materia, carrera, cohorte (not ORM relationships)
            if instance.materia_id:
                mat_stmt = select(Materia).where(Materia.id == instance.materia_id)
                mat_result = await self._session.execute(mat_stmt)
                instance.materia = mat_result.scalar_one_or_none()
            if instance.carrera_id:
                car_stmt = select(Carrera).where(Carrera.id == instance.carrera_id)
                car_result = await self._session.execute(car_stmt)
                instance.carrera = car_result.scalar_one_or_none()
            if instance.cohorte_id:
                coh_stmt = select(Cohorte).where(Cohorte.id == instance.cohorte_id)
                coh_result = await self._session.execute(coh_stmt)
                instance.cohorte = coh_result.scalar_one_or_none()

        return created

    async def clone_equipo(
        self,
        origen_materia_id: uuid.UUID,
        origen_carrera_id: uuid.UUID,
        origen_cohorte_id: uuid.UUID,
        destino_materia_id: uuid.UUID,
        destino_carrera_id: uuid.UUID,
        destino_cohorte_id: uuid.UUID,
        incluir_roles: list[str] | None = None,
    ) -> list[uuid.UUID]:
        """Clone vigentes assignments from origin to destination context.

        - Only clones vigentes (not vencidas, not soft-deleted).
        - Uses cohorte_destino.vig_desde / vig_hasta for dates.
        - Skips duplicates (RN-12): same usuario_id+materia_id+carrera_id+cohorte_id+rol.

        Args:
            origen_*, destino_*: Academic context identifiers.
            incluir_roles: Optional list of role codes to clone (default: all).

        Returns:
            List of newly created Asignacion UUIDs.
        """
        # Get cohorte destino dates
        cohorte_stmt = select(Cohorte).where(
            Cohorte.tenant_id == self._tenant_id,
            Cohorte.id == destino_cohorte_id,
            Cohorte.deleted_at.is_(None),
        )
        result = await self._session.execute(cohorte_stmt)
        cohorte_destino = result.scalar_one_or_none()
        if cohorte_destino is None:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404, detail="Cohorte destino no encontrada"
            )

        # Find vigentes asignaciones in origin
        stmt = self._exclude_deleted(self._stmt()).where(
            Asignacion.materia_id == origen_materia_id,
            Asignacion.carrera_id == origen_carrera_id,
            Asignacion.cohorte_id == origen_cohorte_id,
        )
        today = datetime.now(UTC).date()
        stmt = stmt.where(
            Asignacion.desde <= today,
            (Asignacion.hasta.is_(None)) | (Asignacion.hasta >= today),
        )
        if incluir_roles:
            stmt = stmt.where(Asignacion.rol.in_(incluir_roles))

        result = await self._session.execute(stmt)
        origen_asignaciones = list(result.scalars().all())

        if not origen_asignaciones:
            return []

        # Find existing assignments in destino (for duplicate detection)
        existing_stmt = self._exclude_deleted(self._stmt()).where(
            Asignacion.materia_id == destino_materia_id,
            Asignacion.carrera_id == destino_carrera_id,
            Asignacion.cohorte_id == destino_cohorte_id,
        )
        existing_result = await self._session.execute(existing_stmt)
        existing = list(existing_result.scalars().all())
        existing_keys = {
            (a.usuario_id, a.materia_id, a.carrera_id, a.cohorte_id, a.rol)
            for a in existing
        }

        # Clone, skipping duplicates (RN-12)
        nuevas_ids: list[uuid.UUID] = []
        for orig in origen_asignaciones:
            key = (
                orig.usuario_id,
                destino_materia_id,
                destino_carrera_id,
                destino_cohorte_id,
                orig.rol,
            )
            if key in existing_keys:
                continue

            nueva = await self.create(
                usuario_id=orig.usuario_id,
                rol=orig.rol,
                materia_id=destino_materia_id,
                carrera_id=destino_carrera_id,
                cohorte_id=destino_cohorte_id,
                comisiones=orig.comisiones,
                responsable_id=orig.responsable_id,
                desde=cohorte_destino.vig_desde,
                hasta=cohorte_destino.vig_hasta,
            )
            nuevas_ids.append(nueva.id)
            existing_keys.add(key)

            if len(nuevas_ids) > 200:
                break

        return nuevas_ids

    async def update_vigencia_masiva(
        self,
        materia_id: uuid.UUID | None = None,
        carrera_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
        rol: str | None = None,
        nuevo_desde: date | None = None,
        nuevo_hasta: date | None = None,
        confirmar: bool = False,
    ) -> list[uuid.UUID]:
        """Update vigencia (desde/hasta) for matching asignaciones.

        Args:
            materia_id, carrera_id, cohorte_id, rol: Optional filters.
            nuevo_desde: New start date (optional).
            nuevo_hasta: New end date (optional).
            confirmar: Explicit confirmation flag.

        Returns:
            List of updated Asignacion UUIDs.
        """
        # Protection: if no filters and not confirmado → reject
        has_filters = any(
            x is not None for x in [materia_id, carrera_id, cohorte_id, rol]
        )
        if not has_filters and not confirmar:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail="Actualizar todo el tenant requiere confirmacion explicita (confirmar=true)",
            )

        # Protection: nuevo_desde in the past needs confirmacion
        today = datetime.now(UTC).date()
        if nuevo_desde is not None and nuevo_desde < today and not confirmar:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail="nuevo_desde en el pasado requiere confirmacion explicita (confirmar=true)",
            )

        stmt = self._exclude_deleted(self._stmt())
        if materia_id is not None:
            stmt = stmt.where(Asignacion.materia_id == materia_id)
        if carrera_id is not None:
            stmt = stmt.where(Asignacion.carrera_id == carrera_id)
        if cohorte_id is not None:
            stmt = stmt.where(Asignacion.cohorte_id == cohorte_id)
        if rol is not None:
            stmt = stmt.where(Asignacion.rol == rol)

        result = await self._session.execute(stmt)
        asignaciones = list(result.scalars().all())

        updated_ids: list[uuid.UUID] = []
        for a in asignaciones:
            changed = False
            if nuevo_desde is not None:
                a.desde = nuevo_desde
                changed = True
            if nuevo_hasta is not None:
                a.hasta = nuevo_hasta
                changed = True
            if changed:
                updated_ids.append(a.id)

        await self._session.flush()
        return updated_ids

    async def list_equipo_docente(
        self,
        usuario_id: uuid.UUID,
    ) -> tuple[list[Asignacion], int]:
        """List vigentes asignaciones for a specific user with eager-loaded relations.

        Returns ONLY vigentes assignments (not vencidas, not pendientes, not soft-deleted).

        Args:
            usuario_id: The user whose assignments to list.

        Returns:
            Tuple of (asignaciones list, total count).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(Asignacion.usuario_id == usuario_id)
            .options(
                joinedload(Asignacion.usuario),
                joinedload(Asignacion.responsable),
            )
        )

        today = datetime.now(UTC).date()
        stmt = stmt.where(
            Asignacion.desde <= today,
            (Asignacion.hasta.is_(None)) | (Asignacion.hasta >= today),
        )

        # Count
        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        # Order
        stmt = stmt.order_by(Asignacion.desde.desc())
        result = await self._session.execute(stmt)
        asignaciones = list(result.scalars().all())

        # Eager-load materia, carrera, cohorte for each
        for a in asignaciones:
            if a.materia_id:
                mat_stmt = select(Materia).where(Materia.id == a.materia_id)
                mat_result = await self._session.execute(mat_stmt)
                a.materia = mat_result.scalar_one_or_none()
            if a.carrera_id:
                car_stmt = select(Carrera).where(Carrera.id == a.carrera_id)
                car_result = await self._session.execute(car_stmt)
                a.carrera = car_result.scalar_one_or_none()
            if a.cohorte_id:
                coh_stmt = select(Cohorte).where(Cohorte.id == a.cohorte_id)
                coh_result = await self._session.execute(coh_stmt)
                a.cohorte = coh_result.scalar_one_or_none()

        return asignaciones, total

    async def list_equipos_tenant(
        self,
        skip: int = 0,
        limit: int = 100,
        materia_id: uuid.UUID | None = None,
        carrera_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
        rol: str | None = None,
        docente_id: uuid.UUID | None = None,
        vigentes_only: bool = True,
        q: str | None = None,
    ) -> tuple[list[Asignacion], int]:
        """List all asignaciones in the tenant with advanced filters and search.

        Includes joins to usuario, materia, carrera, cohorte, responsable.
        Supports ILIKE textual search on usuario.display_name and materia.nombre.

        Args:
            skip: Pagination offset.
            limit: Max records (default 100, max 500).
            materia_id, carrera_id, cohorte_id: Academic context filters.
            rol: Filter by role code.
            docente_id: Filter by assigned user.
            vigentes_only: Exclude vencidas and pendientes (default: True).
            q: Text search on usuario name and materia name.

        Returns:
            Tuple of (asignaciones list, total count).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .options(
                joinedload(Asignacion.usuario),
                joinedload(Asignacion.responsable),
            )
        )

        if materia_id is not None:
            stmt = stmt.where(Asignacion.materia_id == materia_id)
        if carrera_id is not None:
            stmt = stmt.where(Asignacion.carrera_id == carrera_id)
        if cohorte_id is not None:
            stmt = stmt.where(Asignacion.cohorte_id == cohorte_id)
        if rol is not None:
            stmt = stmt.where(Asignacion.rol == rol)
        if docente_id is not None:
            stmt = stmt.where(Asignacion.usuario_id == docente_id)

        today = datetime.now(UTC).date()
        if vigentes_only:
            stmt = stmt.where(
                Asignacion.desde <= today,
                (Asignacion.hasta.is_(None)) | (Asignacion.hasta >= today),
            )

        # Text search via ILIKE on user name and materia name.
        # We resolve matching IDs first to avoid join conflicts with joinedload.
        if q:
            search_pattern = f"%{q}%"
            user_sub = select(User.id).where(
                User.tenant_id == self._tenant_id,
                User.deleted_at.is_(None),
                User.display_name.ilike(search_pattern),
            )
            user_ids = [row[0] for row in (await self._session.execute(user_sub)).fetchall()]

            mat_sub = select(Materia.id).where(
                Materia.tenant_id == self._tenant_id,
                Materia.deleted_at.is_(None),
                Materia.nombre.ilike(search_pattern),
            )
            mat_ids = [row[0] for row in (await self._session.execute(mat_sub)).fetchall()]

            conditions = []
            if user_ids:
                conditions.append(Asignacion.usuario_id.in_(user_ids))
            if mat_ids:
                conditions.append(Asignacion.materia_id.in_(mat_ids))

            if conditions:
                stmt = stmt.where(or_(*conditions))
            else:
                # No matches in either — return empty set
                stmt = stmt.where(False)

        # Count
        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        # Paginate
        stmt = stmt.offset(skip).limit(limit).order_by(Asignacion.desde.desc())
        result = await self._session.execute(stmt)
        asignaciones = list(result.scalars().all())

        # Eager-load materia, carrera, cohorte for each
        for a in asignaciones:
            if a.materia_id:
                mat_stmt = select(Materia).where(Materia.id == a.materia_id)
                mat_result = await self._session.execute(mat_stmt)
                a.materia = mat_result.scalar_one_or_none()
            if a.carrera_id:
                car_stmt = select(Carrera).where(Carrera.id == a.carrera_id)
                car_result = await self._session.execute(car_stmt)
                a.carrera = car_result.scalar_one_or_none()
            if a.cohorte_id:
                coh_stmt = select(Cohorte).where(Cohorte.id == a.cohorte_id)
                coh_result = await self._session.execute(coh_stmt)
                a.cohorte = coh_result.scalar_one_or_none()

        return asignaciones, total
