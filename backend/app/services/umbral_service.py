"""Umbral service — threshold management and inheritance resolution.

Coordinates between the repository layer and the API layer.
Provides the get_effective_umbral chain (RN-03) and update logic
with PROFESOR scope enforcement.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.rbac import UserRole as UserRoleModel
from app.models.umbral_materia import UmbralMateria
from app.models.user import User
from app.repositories.umbral_repository import UmbralMateriaRepository
from app.schemas.umbral import UmbralResponse, UmbralUpdateRequest


class UmbralService:
    """Service for managing UmbralMateria configuration.

    All public methods receive db and tenant_id explicitly.
    """

    def __init__(self, db, tenant_id: uuid.UUID):
        self._db = db
        self._tenant_id = tenant_id
        self._repo = UmbralMateriaRepository(session=db, tenant_id=tenant_id)

    async def get_effective_umbral(
        self,
        asignacion_id: uuid.UUID,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> tuple[float, list[str] | None]:
        """Resolve the effective umbral following DN-03 inheritance chain.

        Delegates to the repository for the actual query logic.

        Args:
            asignacion_id: FK to the teaching assignment.
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.

        Returns:
            Tuple of (umbral_pct, valores_aprobatorios).
        """
        return await self._repo.get_effective_umbral(
            asignacion_id=asignacion_id,
            materia_id=materia_id,
            cohorte_id=cohorte_id,
        )

    async def list_umbrales(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> list[UmbralMateria]:
        """List all umbrales for a given (materia, cohorte).

        Args:
            materia_id: FK to Materia.
            cohorte_id: FK to Cohorte.

        Returns:
            List of UmbralMateria records.
        """
        return await self._repo.list_by_filters(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
        )

    async def update_umbral(
        self,
        umbral_id: uuid.UUID,
        data: UmbralUpdateRequest,
        current_user: User,
    ) -> UmbralMateria:
        """Update an existing UmbralMateria with scope enforcement.

        PROFESOR users can only modify umbrales belonging to their own
        teaching assignments. COORDINADOR/ADMIN can modify any.

        Args:
            umbral_id: UUID of the UmbralMateria to update.
            data: Update payload (umbral_pct and/or valores_aprobatorios).
            current_user: The authenticated user (for scope check).

        Returns:
            Updated UmbralMateria instance.

        Raises:
            HTTPException 404: If umbral not found.
            HTTPException 403: If PROFESOR tries to modify another's umbral.
        """
        # Load existing umbral
        umbral = await self._repo.get(umbral_id)
        if umbral is None:
            raise HTTPException(
                status_code=404,
                detail="Umbral no encontrado",
            )

        # Scope check for PROFESOR
        if await self._is_profesor_only(current_user):
            if umbral.asignacion_id is None:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permiso para modificar el umbral global de la materia",
                )
            # Verify this PROFESOR owns this asignacion
            from app.models.asignacion import Asignacion

            stmt = select(Asignacion).where(
                Asignacion.id == umbral.asignacion_id,
                Asignacion.usuario_id == current_user.id,
                Asignacion.tenant_id == self._tenant_id,
                Asignacion.deleted_at.is_(None),
            )
            result = await self._db.execute(stmt)
            if result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permiso para modificar este umbral",
                )

        # Apply updates
        if data.umbral_pct is not None:
            umbral.umbral_pct = data.umbral_pct
        if data.valores_aprobatorios is not None:
            umbral.valores_aprobatorios = data.valores_aprobatorios

        await self._db.flush()
        await self._db.refresh(umbral)
        return umbral

    async def _is_profesor_only(self, user: User) -> bool:
        """Check if a user has PROFESOR role WITHOUT COORDINADOR/ADMIN.

        Args:
            user: The user to check.

        Returns:
            True if PROFESOR only, False if has COORDINADOR or ADMIN.
        """
        stmt = select(UserRoleModel).where(
            UserRoleModel.user_id == user.id,
            UserRoleModel.tenant_id == self._tenant_id,
            UserRoleModel.deleted_at.is_(None),
        ).options(joinedload(UserRoleModel.role))
        result = await self._db.execute(stmt)
        role_codes = {ur.role.codigo for ur in result.scalars().all()}
        return (
            "PROFESOR" in role_codes
            and "COORDINADOR" not in role_codes
            and "ADMIN" not in role_codes
        )
