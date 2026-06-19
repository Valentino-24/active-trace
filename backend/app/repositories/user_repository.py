"""User repository — data access with tenant-aware queries and PII encryption.

Extends BaseRepository[User] with user-specific lookups and automatic
encryption/decryption of PII fields (dni, cuil, cbu, alias_cbu, email).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.core.security import decrypt, encrypt
from app.models.user import User
from app.repositories.base import BaseRepository

# Fields encrypted with AES-256-GCM at rest
_PII_FIELDS = {"email", "dni", "cuil", "cbu", "alias_cbu"}


def _get_encryption_key() -> bytes:
    """Lazy-load the encryption key from settings."""
    from app.core.config import Settings

    key = Settings().encryption_key  # type: ignore[call-arg]
    return key.encode("utf-8")[:32].ljust(32, b"\0")[:32]


def _encrypt_pii(fields: dict[str, Any]) -> dict[str, Any]:
    """Encrypt PII fields in the given dict, modifying in-place."""
    key = _get_encryption_key()
    for field in _PII_FIELDS:
        if field in fields and fields[field] is not None:
            fields[field] = encrypt(str(fields[field]), key)
    return fields


def _decrypt_pii(user: User) -> User:
    """Decrypt PII fields on a User object, modifying in-place."""
    key = _get_encryption_key()
    for field in _PII_FIELDS:
        encrypted = getattr(user, field, None)
        if encrypted is not None:
            try:
                setattr(user, field, decrypt(encrypted, key))
            except Exception:
                # If decryption fails, leave the field as-is (it may be
                # plaintext during migration or testing)
                pass
    return user


class UserRepository(BaseRepository[User]):
    """Repository for User entities with tenant scoping."""

    _model_cls = User

    async def get_by_email(self, email: str) -> User | None:
        """Look up a user by email within the current tenant.

        Uses email_hash for deterministic lookup instead of the
        encrypted email column. The hash is computed server-side.

        Args:
            email: The email address to search for.

        Returns:
            User if found and not deleted, None otherwise.
        """
        email_hash = User.compute_email_hash(email)
        stmt = self._exclude_deleted(self._stmt()).where(
            User.email_hash == email_hash
        )
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is not None:
            _decrypt_pii(user)
        return user

    async def get_by_email_hash(self, email_hash: str) -> User | None:
        """Look up a user by pre-computed email hash."""
        stmt = self._exclude_deleted(self._stmt()).where(
            User.email_hash == email_hash
        )
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is not None:
            _decrypt_pii(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get a user by ID within the current tenant.

        Decrypts PII fields on the returned user.
        """
        user = await self.get(user_id)
        if user is not None:
            _decrypt_pii(user)
        return user

    async def create_user(
        self,
        email: str,
        password_hash: str,
        display_name: str,
        **kwargs: Any,
    ) -> User:
        """Create a new user with PII encryption.

        PII fields (email, dni, cuil, cbu, alias_cbu) are
        automatically encrypted before storage.

        Args:
            email: User's email (will be encrypted).
            password_hash: Argon2id hash.
            display_name: Display name.
            **kwargs: Additional fields (nombre, apellidos, dni, etc.).

        Returns:
            The created User instance with decrypted PII.
        """
        # Compute email hash for lookup
        email_hash = User.compute_email_hash(email)
        data = {
            "email": email,
            "password_hash": password_hash,
            "display_name": display_name,
            "email_hash": email_hash,
            **kwargs,
        }
        _encrypt_pii(data)
        user = await self.create(**data)
        return _decrypt_pii(user)

    async def update_user(
        self, user_id: uuid.UUID, **kwargs: Any
    ) -> User | None:
        """Update a user with PII encryption.

        If email is being updated, also recomputes email_hash.
        PII fields are encrypted before storage.

        Args:
            user_id: UUID of the user to update.
            **kwargs: Fields to update.

        Returns:
            Updated User with decrypted PII, or None if not found.
        """
        # Recompute email_hash if email changed
        if "email" in kwargs and kwargs["email"] is not None:
            kwargs["email_hash"] = User.compute_email_hash(kwargs["email"])

        _encrypt_pii(kwargs)
        user = await self.update(user_id, **kwargs)
        if user is not None:
            _decrypt_pii(user)
        return user

    async def update_password(self, user_id: uuid.UUID, new_hash: str) -> User | None:
        """Update a user's password hash."""
        return await self.update(user_id, password_hash=new_hash)

    async def update_totp(
        self, user_id: uuid.UUID, totp_secret: str | None, totp_enabled: bool
    ) -> User | None:
        """Update TOTP secret and enabled status."""
        return await self.update(
            user_id, totp_secret=totp_secret, totp_enabled=totp_enabled
        )

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        estado: str | None = None,
    ) -> tuple[list[User], int]:
        """List users with optional filtering and pagination.

        Does NOT decrypt PII for list view (use get_by_id for detail).

        Args:
            skip: Number of records to skip.
            limit: Max records to return.
            estado: Optional filter by estado ("activo" / "inactivo").

        Returns:
            Tuple of (users list, total count).
        """
        stmt = self._exclude_deleted(self._stmt())
        if estado is not None:
            stmt = stmt.where(User.estado == estado)

        # Count total
        count_stmt = select(self._model_cls).where(
            self._model_cls.tenant_id == self._tenant_id
        )
        if estado is not None:
            count_stmt = count_stmt.where(User.estado == estado)
        count_result = await self._session.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Paginate
        stmt = stmt.offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def email_exists(self, email: str) -> bool:
        """Check if an email is already registered in this tenant.

        Uses email_hash for deterministic lookup.
        """
        email_hash = User.compute_email_hash(email)
        stmt = self._exclude_deleted(self._stmt()).where(
            User.email_hash == email_hash
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
