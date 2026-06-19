"""User repository — data access with tenant-aware queries.

Extends BaseRepository[User] with user-specific lookups.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User entities with tenant scoping."""

    _model_cls = User

    async def get_by_email(self, email: str) -> User | None:
        """Look up a user by email within the current tenant.

        Args:
            email: The email address to search for.

        Returns:
            User if found and not deleted, None otherwise.
        """
        stmt = self._exclude_deleted(self._stmt()).where(
            User.email == email  # type: ignore[arg-type]
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get a user by ID within the current tenant.

        Args:
            user_id: UUID of the user.

        Returns:
            User if found, None otherwise.
        """
        return await self.get(user_id)

    async def create_user(
        self,
        email: str,
        password_hash: str,
        display_name: str,
        **kwargs: object,
    ) -> User:
        """Create a new user in the current tenant.

        Args:
            email: User's email.
            password_hash: Argon2id hash.
            display_name: Display name.
            **kwargs: Additional fields (is_active, etc.).

        Returns:
            The created User instance.
        """
        return await self.create(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            **kwargs,
        )

    async def update_password(self, user_id: uuid.UUID, new_hash: str) -> User | None:
        """Update a user's password hash.

        Args:
            user_id: UUID of the user.
            new_hash: New Argon2id hash.

        Returns:
            Updated User or None if not found.
        """
        return await self.update(user_id, password_hash=new_hash)

    async def update_totp(
        self, user_id: uuid.UUID, totp_secret: str | None, totp_enabled: bool
    ) -> User | None:
        """Update TOTP secret and enabled status.

        Args:
            user_id: UUID of the user.
            totp_secret: Encrypted TOTP secret (or None to clear).
            totp_enabled: Whether 2FA is enabled.

        Returns:
            Updated User or None if not found.
        """
        return await self.update(
            user_id, totp_secret=totp_secret, totp_enabled=totp_enabled
        )
