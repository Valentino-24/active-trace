"""Tests for User, RefreshToken, and PasswordResetToken models.

RED→GREEN: Write test first, then implement the model.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import User, RefreshToken, PasswordResetToken
from app.models.base import BaseModelMixin, SoftDeleteMixin, TenantScopedMixin
from app.models.tenant import Tenant


class TestUserStructure:
    """RED→GREEN: User model class hierarchy and fields."""

    def test_user_inherits_tenant_scoped_mixin(self):
        """User inherits TenantScopedMixin (has tenant_id)."""
        assert issubclass(User, TenantScopedMixin)

    def test_user_inherits_soft_delete_mixin(self):
        """User inherits SoftDeleteMixin (has deleted_at)."""
        assert issubclass(User, SoftDeleteMixin)

    def test_user_has_email_field(self):
        """User model has email column."""
        assert hasattr(User, "email")

    def test_user_has_password_hash_field(self):
        """User model has password_hash column."""
        assert hasattr(User, "password_hash")

    def test_user_has_totp_fields(self):
        """User has totp_secret (nullable) and totp_enabled columns."""
        assert hasattr(User, "totp_secret")
        assert hasattr(User, "totp_enabled")

    def test_user_has_display_name(self):
        """User has display_name column."""
        assert hasattr(User, "display_name")

    def test_user_has_is_active_field(self):
        """User has is_active column with default True."""
        assert hasattr(User, "is_active")


class TestUserCreate:
    """RED→GREEN: User CRUD and constraints."""

    @pytest.mark.asyncio
    async def test_user_created_with_uuid(self, db_session):
        """User gets an auto-generated UUID primary key."""
        tenant = Tenant(nombre="Test", codigo="U01")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="test@example.com",
            password_hash="argon2hash",
            display_name="Test User",
        )
        db_session.add(user)
        await db_session.flush()
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_user_timestamps_set(self, db_session):
        """created_at and updated_at are populated on persist."""
        tenant = Tenant(nombre="Test", codigo="U02")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="timestamps@example.com",
            password_hash="hash",
            display_name="TS",
        )
        db_session.add(user)
        await db_session.flush()
        assert user.created_at is not None
        assert user.updated_at is not None

    @pytest.mark.asyncio
    async def test_email_unique_per_tenant(self, db_session):
        """Two users with same email in same tenant raises IntegrityError."""
        tenant = Tenant(nombre="Test", codigo="U03")
        db_session.add(tenant)
        await db_session.flush()

        user_a = User(
            tenant_id=tenant.id,
            email="dupe@example.com",
            password_hash="hash1",
            display_name="A",
        )
        user_b = User(
            tenant_id=tenant.id,
            email="dupe@example.com",
            password_hash="hash2",
            display_name="B",
        )
        db_session.add(user_a)
        await db_session.flush()
        db_session.add(user_b)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_same_email_different_tenants_allowed(self, db_session):
        """Two users with same email in DIFFERENT tenants is OK."""
        t1 = Tenant(nombre="T1", codigo="U04A")
        t2 = Tenant(nombre="T2", codigo="U04B")
        db_session.add(t1)
        db_session.add(t2)
        await db_session.flush()

        user_a = User(
            tenant_id=t1.id,
            email="same@example.com",
            password_hash="hash1",
            display_name="A",
        )
        user_b = User(
            tenant_id=t2.id,
            email="same@example.com",
            password_hash="hash2",
            display_name="B",
        )
        db_session.add(user_a)
        db_session.add(user_b)
        await db_session.flush()
        assert user_a.id is not None
        assert user_b.id is not None

    @pytest.mark.asyncio
    async def test_is_active_defaults_true(self, db_session):
        """New user has is_active = True by default."""
        tenant = Tenant(nombre="Test", codigo="U05")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="active@example.com",
            password_hash="hash",
            display_name="Active",
        )
        db_session.add(user)
        await db_session.flush()
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_totp_secret_nullable(self, db_session):
        """totp_secret can be None initially."""
        tenant = Tenant(nombre="Test", codigo="U06")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="nototp@example.com",
            password_hash="hash",
            display_name="NoTOTP",
        )
        db_session.add(user)
        await db_session.flush()
        assert user.totp_secret is None
        assert user.totp_enabled is False

    @pytest.mark.asyncio
    async def test_user_soft_delete(self, db_session):
        """User supports soft delete."""
        tenant = Tenant(nombre="Test", codigo="U07")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="delete@example.com",
            password_hash="hash",
            display_name="Del",
        )
        db_session.add(user)
        await db_session.flush()
        uid = user.id
        user.deleted_at = datetime.now(UTC)
        await db_session.flush()

        result = await db_session.execute(select(User).where(User.id == uid))
        persisted = result.scalar_one()
        assert persisted.deleted_at is not None


class TestRefreshTokenStructure:
    """RED→GREEN: RefreshToken model structure."""

    def test_refresh_token_inherits_base_mixin(self):
        """RefreshToken inherits BaseModelMixin."""
        assert issubclass(RefreshToken, BaseModelMixin)

    def test_refresh_token_has_user_id(self):
        """RefreshToken has user_id FK."""
        assert hasattr(RefreshToken, "user_id")

    def test_refresh_token_has_token_hash(self):
        """RefreshToken has token_hash column."""
        assert hasattr(RefreshToken, "token_hash")

    def test_refresh_token_has_expires_at(self):
        """RefreshToken has expires_at column."""
        assert hasattr(RefreshToken, "expires_at")

    def test_refresh_token_has_revoked_at(self):
        """RefreshToken has revoked_at nullable column."""
        assert hasattr(RefreshToken, "revoked_at")


class TestRefreshTokenCreate:
    """RED→GREEN: RefreshToken persistence."""

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, db_session):
        """Create and persist a RefreshToken."""
        tenant = Tenant(nombre="Test", codigo="RT01")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="rtuser@example.com",
            password_hash="hash",
            display_name="RT",
        )
        db_session.add(user)
        await db_session.flush()

        rt = RefreshToken(
            user_id=user.id,
            token_hash="abcd1234",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(rt)
        await db_session.flush()
        assert rt.id is not None
        assert isinstance(rt.id, uuid.UUID)
        assert rt.revoked_at is None

    @pytest.mark.asyncio
    async def test_revoked_at_set_on_revoke(self, db_session):
        """RefreshToken revoked_at can be set."""
        tenant = Tenant(nombre="Test", codigo="RT02")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="rtuser2@example.com",
            password_hash="hash",
            display_name="RT2",
        )
        db_session.add(user)
        await db_session.flush()

        rt = RefreshToken(
            user_id=user.id,
            token_hash="efgh5678",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(rt)
        await db_session.flush()
        rt.revoked_at = datetime.now(UTC)
        await db_session.flush()
        assert rt.revoked_at is not None


class TestPasswordResetTokenStructure:
    """RED→GREEN: PasswordResetToken model structure."""

    def test_password_reset_token_inherits_base_mixin(self):
        """PasswordResetToken inherits BaseModelMixin."""
        assert issubclass(PasswordResetToken, BaseModelMixin)

    def test_password_reset_token_has_user_id(self):
        """PasswordResetToken has user_id FK."""
        assert hasattr(PasswordResetToken, "user_id")

    def test_password_reset_token_has_token_hash(self):
        """PasswordResetToken has token_hash column."""
        assert hasattr(PasswordResetToken, "token_hash")

    def test_password_reset_token_has_expires_at(self):
        """PasswordResetToken has expires_at column."""
        assert hasattr(PasswordResetToken, "expires_at")

    def test_password_reset_token_has_used_at(self):
        """PasswordResetToken has used_at nullable column."""
        assert hasattr(PasswordResetToken, "used_at")


class TestPasswordResetTokenCreate:
    """RED→GREEN: PasswordResetToken persistence."""

    @pytest.mark.asyncio
    async def test_create_password_reset_token(self, db_session):
        """Create and persist a PasswordResetToken."""
        tenant = Tenant(nombre="Test", codigo="PR01")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="pruser@example.com",
            password_hash="hash",
            display_name="PR",
        )
        db_session.add(user)
        await db_session.flush()

        prt = PasswordResetToken(
            user_id=user.id,
            token_hash="reset1234",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        db_session.add(prt)
        await db_session.flush()
        assert prt.id is not None
        assert prt.used_at is None

    @pytest.mark.asyncio
    async def test_used_at_set_on_use(self, db_session):
        """PasswordResetToken used_at can be set to mark as used."""
        tenant = Tenant(nombre="Test", codigo="PR02")
        db_session.add(tenant)
        await db_session.flush()

        user = User(
            tenant_id=tenant.id,
            email="pruser2@example.com",
            password_hash="hash",
            display_name="PR2",
        )
        db_session.add(user)
        await db_session.flush()

        prt = PasswordResetToken(
            user_id=user.id,
            token_hash="reset5678",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        db_session.add(prt)
        await db_session.flush()
        prt.used_at = datetime.now(UTC)
        await db_session.flush()
        assert prt.used_at is not None
