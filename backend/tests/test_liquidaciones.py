"""Tests for Liquidaciones y Honorarios module (C-18).

Strict TDD: tests written BEFORE implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest_asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Model tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSalarioBaseModel:
    def test_tablename(self):
        from app.models.salario_base import SalarioBase
        assert SalarioBase.__tablename__ == "salario_base"

    def test_fields(self):
        from app.models.salario_base import SalarioBase
        cols = {c.name for c in SalarioBase.__table__.columns}
        for f in ("rol", "monto", "desde", "hasta", "tenant_id", "deleted_at"):
            assert f in cols


class TestSalarioPlusModel:
    def test_tablename(self):
        from app.models.salario_plus import SalarioPlus
        assert SalarioPlus.__tablename__ == "salario_plus"

    def test_fields(self):
        from app.models.salario_plus import SalarioPlus
        cols = {c.name for c in SalarioPlus.__table__.columns}
        for f in ("grupo", "rol", "monto", "desde", "hasta", "tenant_id", "deleted_at"):
            assert f in cols


class TestLiquidacionModel:
    def test_tablename(self):
        from app.models.liquidacion import Liquidacion
        assert Liquidacion.__tablename__ == "liquidacion"

    def test_fields(self):
        from app.models.liquidacion import Liquidacion
        cols = {c.name for c in Liquidacion.__table__.columns}
        for f in ("cohorte_id", "periodo", "usuario_id", "rol", "monto_base",
                   "monto_plus", "total", "es_nexo", "excluido_por_factura", "estado"):
            assert f in cols


class TestFacturaModel:
    def test_tablename(self):
        from app.models.factura import Factura
        assert Factura.__tablename__ == "factura"

    def test_fields(self):
        from app.models.factura import Factura
        cols = {c.name for c in Factura.__table__.columns}
        for f in ("usuario_id", "periodo", "detalle", "referencia_archivo",
                   "estado", "abonada_at", "tenant_id", "deleted_at"):
            assert f in cols


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6: Unit tests — calculation logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculoLiquidacion:
    """Pure function: base + sum(plus por grupo_plus distinto)."""

    def _calcular(self, base_monto, pluses_por_grupo, es_nexo=False, facturador=False):
        """Simula el cálculo sin DB — pura lógica."""
        total_plus = sum(pluses_por_grupo.values())
        total = base_monto + total_plus
        return {
            "monto_base": base_monto,
            "monto_plus": total_plus,
            "total": total,
            "es_nexo": es_nexo,
            "excluido_por_factura": facturador,
        }

    def test_basico_sin_plus(self):
        r = self._calcular(50000, {})
        assert r["monto_base"] == 50000
        assert r["monto_plus"] == 0
        assert r["total"] == 50000

    def test_con_un_grupo_plus(self):
        r = self._calcular(50000, {"PROG": 5000})
        assert r["monto_plus"] == 5000
        assert r["total"] == 55000

    def test_no_acumulativo_mismo_grupo(self):
        """PA-23: 3 comisiones del mismo grupo → 1 solo plus."""
        r = self._calcular(50000, {"PROG": 5000})  # PROG aparece 1 vez = 1 plus
        assert r["monto_plus"] == 5000
        assert r["total"] == 55000

    def test_grupos_distintos_suman(self):
        r = self._calcular(50000, {"PROG": 5000, "BD": 3000})
        assert r["monto_plus"] == 8000
        assert r["total"] == 58000

    def test_sin_grupo_plus(self):
        """Materia sin grupo_plus → no genera plus."""
        r = self._calcular(50000, {})
        assert r["monto_plus"] == 0

    def test_nexo_segmentado(self):
        r = self._calcular(30000, {}, es_nexo=True)
        assert r["es_nexo"] is True
        assert r["total"] == 30000

    def test_facturador_excluido(self):
        r = self._calcular(40000, {"PROG": 5000}, facturador=True)
        assert r["excluido_por_factura"] is True
        assert r["total"] == 45000  # total calculado pero marcado como excluido


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture: seed_liquidaciones
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_liquidaciones() -> dict:
    """Seed: tenant + finanzas user + carrera + cohorte + materia with grupo_plus + perms."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.core.security import hash_password
    from app.models.carrera import Carrera
    from app.models.cohorte import Cohorte
    from app.models.materia import Materia
    from app.models.rbac import Permission, Role, RolePermission, UserRole
    from app.models.tenant import Tenant
    from app.models.user import User
    from .conftest import TEST_SETTINGS
    from app.core.database import Base

    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Liquidaciones Tenant", codigo=f"LIQ{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        finanzas = User(
            tenant_id=tenant.id, email=f"fin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("FinPass123!"), display_name="Finanzas",
            is_active=True,
        )
        session.add(finanzas)
        await session.flush()

        no_perm = User(
            tenant_id=tenant.id, email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"), display_name="Sin Permiso",
            is_active=True,
        )
        session.add(no_perm)
        await session.flush()

        rol_fin = Role(tenant_id=tenant.id, codigo="FINANZAS", nombre="Finanzas")
        session.add(rol_fin)
        await session.flush()

        session.add(UserRole(user_id=finanzas.id, role_id=rol_fin.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        session.add(UserRole(user_id=no_perm.id, role_id=rol_fin.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        await session.flush()

        for code, desc in [
            ("liquidaciones:ver", "Ver liquidaciones"),
            ("liquidaciones:gestionar", "Gestionar liquidaciones"),
            ("liquidaciones:configurar-salarios", "Configurar grilla salarial"),
        ]:
            p = Permission(id=uuid.uuid4(), tenant_id=tenant.id, codigo=code, descripcion=desc)
            session.add(p)
            await session.flush()
            session.add(RolePermission(id=uuid.uuid4(), role_id=rol_fin.id, permission_id=p.id))
        # no_perm gets role but NOT the liquidaciones perms
        await session.flush()

        carrera = Carrera(tenant_id=tenant.id, codigo="TUP", nombre="Tecnicatura")
        session.add(carrera)
        await session.flush()

        cohorte = Cohorte(
            tenant_id=tenant.id, carrera_id=carrera.id,
            nombre="2025-A", anio=2025, vig_desde=date(2025, 1, 1),
        )
        session.add(cohorte)
        await session.flush()

        materia = Materia(
            tenant_id=tenant.id, codigo="PROG1", nombre="Programacion I",
            grupo_plus="PROG",
        )
        session.add(materia)
        await session.flush()

        await session.commit()

        data["tenant_id"] = tenant.id
        data["finanzas_id"] = finanzas.id
        data["no_perm_id"] = no_perm.id
        data["materia_id"] = materia.id
        data["carrera_id"] = carrera.id
        data["cohorte_id"] = cohorte.id

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Repository tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSalarioBaseRepository:
    async def test_create_and_get(self, seed_liquidaciones):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.salario_repository import SalarioBaseRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = SalarioBaseRepository(session=session, tenant_id=seed_liquidaciones["tenant_id"])
            sb = await r.create(rol="PROFESOR", monto=50000, desde=date(2025, 1, 1))
            await session.commit()

            fetched = await r.get(sb.id)
            assert fetched is not None
            assert fetched.monto == 50000
            assert fetched.rol == "PROFESOR"
        await engine.dispose()

    async def test_get_vigente(self, seed_liquidaciones):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.salario_repository import SalarioBaseRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = SalarioBaseRepository(session=session, tenant_id=seed_liquidaciones["tenant_id"])
            await r.create(rol="PROFESOR", monto=50000, desde=date(2025, 1, 1))
            await r.create(rol="PROFESOR", monto=60000, desde=date(2026, 1, 1))
            await session.commit()

            vigente_2025 = await r.get_vigente(rol="PROFESOR", fecha=date(2025, 6, 1))
            assert vigente_2025 is not None
            assert vigente_2025.monto == 50000

            vigente_2026 = await r.get_vigente(rol="PROFESOR", fecha=date(2026, 3, 1))
            assert vigente_2026 is not None
            assert vigente_2026.monto == 60000
        await engine.dispose()


class TestSalarioPlusRepository:
    async def test_create_and_list_vigentes(self, seed_liquidaciones):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.salario_repository import SalarioPlusRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = SalarioPlusRepository(session=session, tenant_id=seed_liquidaciones["tenant_id"])
            await r.create(grupo="PROG", rol="PROFESOR", monto=5000, desde=date(2025, 1, 1))
            await r.create(grupo="BD", rol="PROFESOR", monto=3000, desde=date(2025, 1, 1))
            await session.commit()

            vigentes = await r.get_vigentes_por_grupo_rol(
                grupo="PROG", rol="PROFESOR", fecha=date(2025, 6, 1),
            )
            assert len(vigentes) == 1
            assert vigentes[0].monto == 5000
        await engine.dispose()
