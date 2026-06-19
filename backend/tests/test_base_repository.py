"""Tests for BaseRepository generic async repository.

Tests use a lightweight test entity (TestItem) registered on Base.metadata
to verify multi-tenant isolation, CRUD operations, and soft delete behavior.
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import String, select
from sqlalchemy.dialects.postgresql import UUID as UUIDType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TenantScopedMixin
from app.models.tenant import Tenant
from app.repositories import BaseRepository

# ── Test entity ──────────────────────────────────────────────────────────────


class TestItem(Base, TenantScopedMixin, SoftDeleteMixin):
    """Lightweight entity for repository tests. Registered on Base.metadata."""

    __tablename__ = "test_item"

    name: Mapped[str] = mapped_column(String(100), nullable=False)


# ── Concrete repository for the test entity ──────────────────────────────────


class TestItemRepository(BaseRepository[TestItem]):
    _model_cls = TestItem


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def tenant_a(db_session) -> Tenant:
    """Creates a real Tenant in the DB for test isolation."""
    tenant = Tenant(nombre="Tenant A", codigo="TENANT_A")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def tenant_b(db_session) -> Tenant:
    """Creates another Tenant in the DB for test isolation."""
    tenant = Tenant(nombre="Tenant B", codigo="TENANT_B")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def tenant_a_id(tenant_a: Tenant) -> uuid.UUID:
    return tenant_a.id


@pytest_asyncio.fixture
async def tenant_b_id(tenant_b: Tenant) -> uuid.UUID:
    return tenant_b.id


@pytest_asyncio.fixture
async def repo_a(db_session, tenant_a_id: uuid.UUID) -> TestItemRepository:
    return TestItemRepository(session=db_session, tenant_id=tenant_a_id)


@pytest_asyncio.fixture
async def repo_b(db_session, tenant_b_id: uuid.UUID) -> TestItemRepository:
    return TestItemRepository(session=db_session, tenant_id=tenant_b_id)


# ── Tests ────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    """RED→GREEN: Two tenants must NOT see each other's data."""

    @pytest.mark.asyncio
    async def test_tenant_a_does_not_see_tenant_b_data(
        self, repo_a, repo_b, tenant_a_id, tenant_b_id
    ):
        """Data created for tenant B is invisible to tenant A."""
        # Arrange
        await repo_b.create(name="B's item")
        # Act
        items_a = await repo_a.list()
        # Assert
        assert len(items_a) == 0

    @pytest.mark.asyncio
    async def test_tenant_b_does_not_see_tenant_a_data(
        self, repo_a, repo_b, tenant_a_id, tenant_b_id
    ):
        """Data created for tenant A is invisible to tenant B."""
        await repo_a.create(name="A's item")
        items_b = await repo_b.list()
        assert len(items_b) == 0

    @pytest.mark.asyncio
    async def test_tenant_gets_own_data(
        self, repo_a, repo_b, tenant_a_id, tenant_b_id
    ):
        """Each tenant sees only its own records."""
        await repo_a.create(name="A-1")
        await repo_a.create(name="A-2")
        await repo_b.create(name="B-1")
        items_a = await repo_a.list()
        items_b = await repo_b.list()
        assert len(items_a) == 2
        assert len(items_b) == 1
        names_a = {item.name for item in items_a}
        assert names_a == {"A-1", "A-2"}


class TestCreate:
    """RED→GREEN: create assigns tenant_id and persists."""

    @pytest.mark.asyncio
    async def test_create_assigns_tenant_id_automatically(
        self, repo_a, tenant_a_id, db_session
    ):
        """create() auto-assigns tenant_id from repository."""
        item = await repo_a.create(name="Auto Tenant")
        assert item.tenant_id == tenant_a_id
        # Double-check in DB
        result = await db_session.execute(
            select(TestItem).where(TestItem.id == item.id)
        )
        persisted = result.scalar_one()
        assert persisted.tenant_id == tenant_a_id

    @pytest.mark.asyncio
    async def test_create_assigned_id_is_uuid(self, repo_a):
        """New item gets a UUID primary key."""
        item = await repo_a.create(name="UUID Check")
        assert item.id is not None
        assert isinstance(item.id, uuid.UUID)

    @pytest.mark.asyncio
    async def test_create_sets_timestamps(self, repo_a):
        """Created item has created_at and updated_at populated."""
        item = await repo_a.create(name="Timestamp Check")
        assert item.created_at is not None
        assert item.updated_at is not None


class TestGet:
    """RED→GREEN: get retrieves by id within tenant scope."""

    @pytest.mark.asyncio
    async def test_get_returns_item(self, repo_a):
        """get() returns the item for this tenant."""
        item = await repo_a.create(name="Get Me")
        found = await repo_a.get(item.id)
        assert found is not None
        assert found.id == item.id

    @pytest.mark.asyncio
    async def test_get_returns_none_for_wrong_id(self, repo_a):
        """get() returns None when id does not exist."""
        found = await repo_a.get(uuid.uuid4())
        assert found is None

    @pytest.mark.asyncio
    async def test_get_returns_none_for_other_tenant(
        self, repo_a, repo_b
    ):
        """get() does NOT return an item from another tenant."""
        item = await repo_a.create(name="Other Tenant")
        found = await repo_b.get(item.id)
        assert found is None


class TestUpdate:
    """GREEN: update modifies fields and returns updated instance."""

    @pytest.mark.asyncio
    async def test_update_modifies_field(self, repo_a):
        """update() changes a field value."""
        item = await repo_a.create(name="Old Name")
        updated = await repo_a.update(item.id, name="New Name")
        assert updated is not None
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_returns_none_if_not_found(self, repo_a):
        """update() with non-existent id returns None."""
        result = await repo_a.update(uuid.uuid4(), name="Ghost")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_does_not_cross_tenants(self, repo_a, repo_b):
        """Cannot update a record from another tenant."""
        item = await repo_a.create(name="Secret")
        result = await repo_b.update(item.id, name="Hacked")
        assert result is None


class TestSoftDelete:
    """RED→GREEN→TRIANGULATE: soft delete marks deleted_at."""

    @pytest.mark.asyncio
    async def test_soft_delete_sets_deleted_at(self, repo_a):
        """soft_delete() sets deleted_at timestamp."""
        item = await repo_a.create(name="Delete Me")
        result = await repo_a.soft_delete(item.id)
        assert result is True
        assert item.deleted_at is not None

    @pytest.mark.asyncio
    async def test_get_returns_none_after_soft_delete(self, repo_a):
        """After soft_delete, get() returns None."""
        item = await repo_a.create(name="Gone")
        await repo_a.soft_delete(item.id)
        found = await repo_a.get(item.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_list_excludes_soft_deleted(self, repo_a):
        """list() does NOT include soft-deleted records."""
        await repo_a.create(name="Keep")
        item2 = await repo_a.create(name="Remove")
        await repo_a.soft_delete(item2.id)
        items = await repo_a.list()
        names = [i.name for i in items]
        assert "Remove" not in names
        assert "Keep" in names

    @pytest.mark.asyncio
    async def test_soft_delete_does_not_remove_from_db(self, repo_a, db_session):
        """Soft-deleted record still exists in the database."""
        item = await repo_a.create(name="Still There")
        await repo_a.soft_delete(item.id)
        result = await db_session.execute(
            select(TestItem).where(TestItem.id == item.id)
        )
        persisted = result.scalar_one()
        assert persisted is not None
        assert persisted.deleted_at is not None

    @pytest.mark.asyncio
    async def test_soft_delete_returns_false_for_missing(self, repo_a):
        """soft_delete() returns False for non-existent id."""
        result = await repo_a.soft_delete(uuid.uuid4())
        assert result is False
