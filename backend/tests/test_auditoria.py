"""Tests for Panel de Auditoria y Metricas (C-19)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest_asyncio


class TestScopeAuditoria:
    """Scope: ADMIN sees all, COORDINADOR sees only own actions."""

    def _aplicar_scope(self, es_admin, actor_id, registros):
        if es_admin:
            return registros
        return [r for r in registros if r["actor_id"] == actor_id]

    def test_admin_ve_todo(self):
        regs = [{"actor_id": "A", "accion": "X"}, {"actor_id": "B", "accion": "Y"}]
        result = self._aplicar_scope(True, "A", regs)
        assert len(result) == 2

    def test_coordinador_ve_solo_propio(self):
        regs = [{"actor_id": "A", "accion": "X"}, {"actor_id": "B", "accion": "Y"}]
        result = self._aplicar_scope(False, "A", regs)
        assert len(result) == 1
        assert result[0]["actor_id"] == "A"

    def test_coordinador_sin_acciones(self):
        regs = [{"actor_id": "B", "accion": "X"}]
        result = self._aplicar_scope(False, "A", regs)
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_auditoria() -> dict:
    """Seed: tenant + admin + coordinador + audit_log entries + permiso."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.core.security import hash_password
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.rbac import Permission, Role, RolePermission, UserRole
    from app.models.audit_log import AuditLog
    from .conftest import TEST_SETTINGS
    from app.core.database import Base

    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Audit Tenant", codigo=f"AU{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        admin = User(
            tenant_id=tenant.id, email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("Admin123!"), display_name="Admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        coord = User(
            tenant_id=tenant.id, email=f"coord-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("Coord123!"), display_name="Coordinador",
            is_active=True,
        )
        session.add(coord)
        await session.flush()

        no_perm = User(
            tenant_id=tenant.id, email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"), display_name="SinPerm",
            is_active=True,
        )
        session.add(no_perm)
        await session.flush()

        rol_admin = Role(tenant_id=tenant.id, codigo="ADMIN", nombre="Admin")
        rol_coord = Role(tenant_id=tenant.id, codigo="COORDINADOR", nombre="Coordinador")
        session.add_all([rol_admin, rol_coord])
        await session.flush()

        session.add(UserRole(user_id=admin.id, role_id=rol_admin.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        session.add(UserRole(user_id=coord.id, role_id=rol_coord.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        session.add(UserRole(user_id=no_perm.id, role_id=rol_coord.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        await session.flush()

        perm = Permission(id=uuid.uuid4(), tenant_id=tenant.id, codigo="auditoria:ver", descripcion="Ver auditoria")
        session.add(perm)
        await session.flush()

        session.add(RolePermission(id=uuid.uuid4(), role_id=rol_admin.id, permission_id=perm.id))
        session.add(RolePermission(id=uuid.uuid4(), role_id=rol_coord.id, permission_id=perm.id))
        await session.flush()

        # Seed audit log entries
        ahora = datetime(2025, 6, 15, 10, 0, 0)
        for i in range(5):
            session.add(AuditLog(
                tenant_id=tenant.id, actor_id=admin.id,
                accion="CALIFICACIONES_IMPORTAR" if i < 3 else "TAREA_CREAR",
                fecha_hora=ahora + timedelta(hours=i),
                filas_afectadas=10 + i,
            ))
        for i in range(3):
            session.add(AuditLog(
                tenant_id=tenant.id, actor_id=coord.id,
                accion="COMUNICACION_ENVIAR",
                fecha_hora=ahora + timedelta(days=1, hours=i),
                filas_afectadas=1,
            ))
        await session.commit()

        data["tenant_id"] = tenant.id
        data["admin_id"] = admin.id
        data["coord_id"] = coord.id
        data["no_perm_id"] = no_perm.id

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Repository tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditoriaRepository:
    async def test_acciones_por_dia(self, seed_auditoria):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.audit_log_repository import AuditLogRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AuditLogRepository(session=session, tenant_id=seed_auditoria["tenant_id"])
            result = await repo.acciones_por_dia()
            assert len(result) >= 1
            assert "fecha" in result[0]
            assert "total" in result[0]
        await engine.dispose()

    async def test_recientes(self, seed_auditoria):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.audit_log_repository import AuditLogRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AuditLogRepository(session=session, tenant_id=seed_auditoria["tenant_id"])
            items = await repo.recientes(limit=3)
            assert len(items) <= 3
            # Should be most recent first
            if len(items) >= 2:
                assert items[0].fecha_hora >= items[1].fecha_hora
        await engine.dispose()

    async def test_list_con_filtros(self, seed_auditoria):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.audit_log_repository import AuditLogRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AuditLogRepository(session=session, tenant_id=seed_auditoria["tenant_id"])
            all_items = await repo.list_con_filtros()
            assert len(all_items) == 8

            filtered = await repo.list_con_filtros(accion="CALIFICACIONES_IMPORTAR")
            assert len(filtered) == 3

            by_actor = await repo.list_con_filtros(usuario_id=seed_auditoria["coord_id"])
            assert len(by_actor) == 3
        await engine.dispose()
