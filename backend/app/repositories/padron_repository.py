"""Padron repositories — tenant-scoped data access for versioned student rosters.

Provides VersionPadronRepository and EntradaPadronRepository for managing
versioned padron imports and their student entries.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import joinedload

from app.core.security import encrypt
from app.models.padron import EntradaPadron, VersionPadron
from app.models.user import User
from app.repositories.base import BaseRepository


def _get_encryption_key() -> bytes:
    """Derive exactly 32 bytes for AES-256 from the settings key material.

    Uses SHA-256 to deterministically produce a 32-byte key from any
    arbitrary-length key material stored in settings.
    """
    from app.core.config import Settings

    settings = Settings()  # type: ignore[call-arg]
    key_material = settings.encryption_key  # type: ignore[union-attr]
    return hashlib.sha256(key_material.encode("utf-8")).digest()


class VersionPadronRepository(BaseRepository[VersionPadron]):
    """Repository for versioned padron imports."""

    _model_cls = VersionPadron

    async def create_version(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
        cargado_por: uuid.UUID,
        modo: str,
    ) -> VersionPadron:
        """Create a new active padron version.

        The new version is created with activa=true.
        The previous active version for the same (materia, cohorte)
        is automatically deactivated.

        Args:
            materia_id: FK to materia.
            cohorte_id: FK to cohorte.
            cargado_por: FK to the importing user.
            modo: 'moodle_ws' or 'archivo'.

        Returns:
            The newly created VersionPadron.
        """
        # Deactivate previous active version
        await self.deactivate_previous(materia_id, cohorte_id)

        # Create new version
        version = await self.create(
            materia_id=materia_id,
            cohorte_id=cohorte_id,
            cargado_por=cargado_por,
            cargado_at=datetime.now(UTC),
            activa=True,
            modo=modo,
        )
        return version

    async def deactivate_previous(
        self,
        materia_id: uuid.UUID,
        cohorte_id: uuid.UUID,
    ) -> int:
        """Deactivate the currently active version for (materia, cohorte).

        Args:
            materia_id: FK to materia.
            cohorte_id: FK to cohorte.

        Returns:
            Number of versions deactivated (0 or 1).
        """
        stmt = (
            update(VersionPadron)
            .where(
                VersionPadron.tenant_id == self._tenant_id,
                VersionPadron.materia_id == materia_id,
                VersionPadron.cohorte_id == cohorte_id,
                VersionPadron.activa.is_(True),
                VersionPadron.deleted_at.is_(None),
            )
            .values(activa=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]

    async def list_versiones(
        self,
        materia_id: uuid.UUID | None = None,
        cohorte_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[VersionPadron], int]:
        """List padron versions with optional filters and pagination.

        Args:
            materia_id: Filter by materia (optional).
            cohorte_id: Filter by cohorte (optional).
            skip: Pagination offset.
            limit: Max records to return.

        Returns:
            Tuple of (versions list, total count).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .options(joinedload(VersionPadron.cargador))
            .order_by(VersionPadron.cargado_at.desc())
        )

        if materia_id is not None:
            stmt = stmt.where(VersionPadron.materia_id == materia_id)
        if cohorte_id is not None:
            stmt = stmt.where(VersionPadron.cohorte_id == cohorte_id)

        # Count
        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        # Paginate
        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        versions = list(result.scalars().all())

        return versions, total

    async def get_version_detail(
        self,
        version_id: uuid.UUID,
    ) -> VersionPadron | None:
        """Get a version with its cargador relationship loaded.

        Args:
            version_id: UUID of the version.

        Returns:
            VersionPadron with cargador loaded, or None.
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(VersionPadron.id == version_id)
            .options(joinedload(VersionPadron.cargador))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete_by_materia(
        self,
        materia_id: uuid.UUID,
        cargado_por: uuid.UUID | None = None,
    ) -> int:
        """Soft-delete all versions for a materia (optionally filtered by user).

        Args:
            materia_id: FK to materia.
            cargado_por: If set, only delete versions by this user (PROFESOR scope).

        Returns:
            Number of versions soft-deleted.
        """
        stmt = (
            select(VersionPadron)
            .where(
                VersionPadron.tenant_id == self._tenant_id,
                VersionPadron.materia_id == materia_id,
                VersionPadron.deleted_at.is_(None),
            )
        )
        if cargado_por is not None:
            stmt = stmt.where(VersionPadron.cargado_por == cargado_por)

        result = await self._session.execute(stmt)
        versions = list(result.scalars().all())

        now = datetime.now(UTC)
        for v in versions:
            v.deleted_at = now

        await self._session.flush()
        return len(versions)


class EntradaPadronRepository(BaseRepository[EntradaPadron]):
    """Repository for individual padron entries."""

    _model_cls = EntradaPadron

    async def bulk_create_from_import(
        self,
        version_id: uuid.UUID,
        filas: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Create multiple EntradaPadron rows from import data.

        For each row:
        - Encrypts email with AES-256-GCM
        - Computes email_hash for user matching
        - Attempts to match against users table by email_hash
        - Stores usuario_id if matched, else NULL

        Args:
            version_id: FK to the parent VersionPadron.
            filas: List of dicts with keys:
                   nombre, apellidos, email, comision, regional.

        Returns:
            Tuple of (total_created, total_without_user).
        """
        key = _get_encryption_key()
        total_sin_usuario = 0

        for fila in filas:
            email = fila.get("email", "")
            email_hash = User.compute_email_hash(email) if email else ""
            email_cifrado = encrypt(email, key) if email else None

            # Try to match by email_hash
            usuario_id = await self._match_by_email_hash(email_hash)

            if usuario_id is None:
                total_sin_usuario += 1

            await self.create(
                version_id=version_id,
                usuario_id=usuario_id,
                nombre=fila.get("nombre", ""),
                apellidos=fila.get("apellidos", ""),
                email_cifrado=email_cifrado,
                email_hash=email_hash,
                comision=fila.get("comision"),
                regional=fila.get("regional"),
            )

        return len(filas), total_sin_usuario

    async def _match_by_email_hash(
        self,
        email_hash: str,
    ) -> uuid.UUID | None:
        """Look up a user by email_hash within the current tenant.

        Args:
            email_hash: SHA-256 hash of the email.

        Returns:
            User UUID if found, None otherwise.
        """
        if not email_hash:
            return None

        stmt = select(User.id).where(
            User.tenant_id == self._tenant_id,
            User.email_hash == email_hash,
            User.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        return row[0] if row else None

    async def list_entradas_by_version(
        self,
        version_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[EntradaPadron], int]:
        """List entries for a specific version with pagination.

        Args:
            version_id: FK to the parent VersionPadron.
            skip: Pagination offset.
            limit: Max records to return.

        Returns:
            Tuple of (entradas list, total count).
        """
        stmt = (
            self._exclude_deleted(self._stmt())
            .where(EntradaPadron.version_id == version_id)
            .options(joinedload(EntradaPadron.usuario))
            .order_by(EntradaPadron.apellidos, EntradaPadron.nombre)
        )

        # Count
        count_result = await self._session.execute(stmt)
        total = len(count_result.scalars().all())

        # Paginate
        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        entradas = list(result.scalars().all())

        return entradas, total

    async def soft_delete_by_materia(
        self,
        materia_id: uuid.UUID,
        cargado_por: uuid.UUID | None = None,
    ) -> int:
        """Soft-delete all entries linked to versions of a materia.

        Args:
            materia_id: FK to materia.
            cargado_por: If set, only delete entries from versions by this user.

        Returns:
            Number of entries soft-deleted.
        """
        # Subquery: find version IDs for this materia
        version_stmt = (
            select(VersionPadron.id)
            .where(
                VersionPadron.tenant_id == self._tenant_id,
                VersionPadron.materia_id == materia_id,
            )
        )
        if cargado_por is not None:
            version_stmt = version_stmt.where(
                VersionPadron.cargado_por == cargado_por
            )

        version_result = await self._session.execute(version_stmt)
        version_ids = [row[0] for row in version_result.fetchall()]

        if not version_ids:
            return 0

        stmt = select(EntradaPadron).where(
            EntradaPadron.tenant_id == self._tenant_id,
            EntradaPadron.version_id.in_(version_ids),
            EntradaPadron.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        entradas = list(result.scalars().all())

        now = datetime.now(UTC)
        for e in entradas:
            e.deleted_at = now

        await self._session.flush()
        return len(entradas)
