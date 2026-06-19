"""Tests for Programas y Fechas Academicas module (C-17).

Strict TDD: tests written BEFORE implementation.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest_asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Model tests (Tasks 1.1 & 1.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTipoFechaEnum:
    """TipoFecha enum — Parcial|TP|Coloquio|Recuperatorio."""

    def test_enum_values(self):
        from app.models.fecha_academica import TipoFecha
        assert TipoFecha.Parcial.value == "Parcial"
        assert TipoFecha.TP.value == "TP"
        assert TipoFecha.Coloquio.value == "Coloquio"
        assert TipoFecha.Recuperatorio.value == "Recuperatorio"


class TestProgramaMateriaModel:
    """ProgramaMateria model — structural tests."""

    def test_tablename(self):
        from app.models.programa_materia import ProgramaMateria
        assert ProgramaMateria.__tablename__ == "programa_materia"

    def test_fields_exist(self):
        from app.models.programa_materia import ProgramaMateria
        cols = {c.name for c in ProgramaMateria.__table__.columns}
        assert "materia_id" in cols
        assert "carrera_id" in cols
        assert "cohorte_id" in cols
        assert "titulo" in cols
        assert "referencia_archivo" in cols
        assert "tenant_id" in cols
        assert "deleted_at" in cols  # soft delete


class TestFechaAcademicaModel:
    """FechaAcademica model — structural tests."""

    def test_tablename(self):
        from app.models.fecha_academica import FechaAcademica
        assert FechaAcademica.__tablename__ == "fecha_academica"

    def test_fields_exist(self):
        from app.models.fecha_academica import FechaAcademica
        cols = {c.name for c in FechaAcademica.__table__.columns}
        assert "materia_id" in cols
        assert "cohorte_id" in cols
        assert "tipo" in cols
        assert "numero" in cols
        assert "periodo" in cols
        assert "fecha" in cols
        assert "titulo" in cols
        assert "tenant_id" in cols
        assert "deleted_at" in cols


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture: seed_academic
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_academic() -> dict:
    """Seed: tenant + admin user + carrera + cohorte + materia + permiso."""
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
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Academic Tenant", codigo=f"AC{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        coord = User(
            tenant_id=tenant.id, email=f"coord-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("CoordPass123!"), display_name="Coordinador",
            is_active=True,
        )
        session.add(coord)
        await session.flush()

        no_perm = User(
            tenant_id=tenant.id, email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"), display_name="Sin Permiso",
            is_active=True,
        )
        session.add(no_perm)
        await session.flush()

        rol_coord = Role(tenant_id=tenant.id, codigo="COORDINADOR", nombre="Coordinador")
        session.add(rol_coord)
        await session.flush()

        session.add(UserRole(user_id=coord.id, role_id=rol_coord.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        session.add(UserRole(user_id=no_perm.id, role_id=rol_coord.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        await session.flush()

        perm = Permission(
            id=uuid.uuid4(), tenant_id=tenant.id,
            codigo="estructura:gestionar", descripcion="Gestionar estructura academica",
        )
        session.add(perm)
        await session.flush()

        session.add(RolePermission(id=uuid.uuid4(), role_id=rol_coord.id, permission_id=perm.id))
        # no_perm gets ROLE but NOT the permission (test 403)
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

        materia = Materia(tenant_id=tenant.id, codigo="PROG1", nombre="Programacion I")
        session.add(materia)
        await session.flush()

        await session.commit()

        data["tenant_id"] = tenant.id
        data["coord_id"] = coord.id
        data["no_perm_id"] = no_perm.id
        data["materia_id"] = materia.id
        data["carrera_id"] = carrera.id
        data["cohorte_id"] = cohorte.id

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Repository tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProgramaRepository:
    """ProgramaRepository — CRUD, list_con_filtros."""

    async def test_create_and_get(self, seed_academic):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.programa_repository import ProgramaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = ProgramaRepository(session=session, tenant_id=seed_academic["tenant_id"])
            prog = await r.create(
                materia_id=seed_academic["materia_id"],
                carrera_id=seed_academic["carrera_id"],
                cohorte_id=seed_academic["cohorte_id"],
                titulo="Programa 2025",
                referencia_archivo="/docs/prog1.pdf",
            )
            await session.commit()

            fetched = await r.get(prog.id)
            assert fetched is not None
            assert fetched.titulo == "Programa 2025"
            assert fetched.referencia_archivo == "/docs/prog1.pdf"
        await engine.dispose()

    async def test_list_con_filtros(self, seed_academic):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.programa_repository import ProgramaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = ProgramaRepository(session=session, tenant_id=seed_academic["tenant_id"])
            await r.create(
                materia_id=seed_academic["materia_id"],
                carrera_id=seed_academic["carrera_id"],
                cohorte_id=seed_academic["cohorte_id"],
                titulo="P1", referencia_archivo="/p1.pdf",
            )
            await r.create(
                materia_id=seed_academic["materia_id"],
                carrera_id=seed_academic["carrera_id"],
                cohorte_id=seed_academic["cohorte_id"],
                titulo="P2", referencia_archivo="/p2.pdf",
            )
            await session.commit()

            all_progs = await r.list_con_filtros(tenant_id=seed_academic["tenant_id"])
            assert len(all_progs) == 2

            filtered = await r.list_con_filtros(
                tenant_id=seed_academic["tenant_id"],
                materia_id=seed_academic["materia_id"],
                cohorte_id=seed_academic["cohorte_id"],
            )
            assert len(filtered) == 2
        await engine.dispose()


class TestFechaRepository:
    """FechaRepository — CRUD, list_con_filtros with tipo and periodo."""

    async def test_create_and_get(self, seed_academic):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.fecha_repository import FechaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = FechaRepository(session=session, tenant_id=seed_academic["tenant_id"])
            fecha = await r.create(
                materia_id=seed_academic["materia_id"],
                cohorte_id=seed_academic["cohorte_id"],
                tipo="Parcial", numero=1, periodo="2025-1",
                fecha=date(2025, 5, 15), titulo="1er Parcial",
            )
            await session.commit()

            fetched = await r.get(fecha.id)
            assert fetched is not None
            assert fetched.tipo == "Parcial"
            assert fetched.numero == 1
            assert fetched.periodo == "2025-1"
        await engine.dispose()

    async def test_list_con_filtros(self, seed_academic):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.fecha_repository import FechaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = FechaRepository(session=session, tenant_id=seed_academic["tenant_id"])
            await r.create(
                materia_id=seed_academic["materia_id"],
                cohorte_id=seed_academic["cohorte_id"],
                tipo="Parcial", numero=1, periodo="2025-1",
                fecha=date(2025, 5, 15), titulo="1er Parcial",
            )
            await r.create(
                materia_id=seed_academic["materia_id"],
                cohorte_id=seed_academic["cohorte_id"],
                tipo="TP", numero=1, periodo="2025-1",
                fecha=date(2025, 6, 10), titulo="TP1",
            )
            await r.create(
                materia_id=seed_academic["materia_id"],
                cohorte_id=seed_academic["cohorte_id"],
                tipo="Parcial", numero=2, periodo="2025-2",
                fecha=date(2025, 10, 20), titulo="2do Parcial",
            )
            await session.commit()

            # Filter by tipo
            parciales = await r.list_con_filtros(
                tenant_id=seed_academic["tenant_id"], tipo="Parcial",
            )
            assert len(parciales) == 2

            # Filter by periodo
            p1 = await r.list_con_filtros(
                tenant_id=seed_academic["tenant_id"], periodo="2025-1",
            )
            assert len(p1) == 2

            # Combined filters
            combined = await r.list_con_filtros(
                tenant_id=seed_academic["tenant_id"], tipo="Parcial", periodo="2025-2",
            )
            assert len(combined) == 1
            assert combined[0].titulo == "2do Parcial"

            # By materia
            by_mat = await r.list_con_filtros(
                tenant_id=seed_academic["tenant_id"], materia_id=seed_academic["materia_id"],
            )
            assert len(by_mat) == 3
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Schema tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProgramasFechasSchemas:
    """Schema validation tests."""

    def test_programa_request_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.programas_fechas import ProgramaCrearRequest
        try:
            ProgramaCrearRequest(
                materia_id=uuid.uuid4(), carrera_id=uuid.uuid4(),
                cohorte_id=uuid.uuid4(), titulo="P",
                extra="boom",
            )
            assert False
        except ValidationError:
            pass

    def test_fecha_request_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.programas_fechas import FechaCrearRequest
        try:
            FechaCrearRequest(
                materia_id=uuid.uuid4(), cohorte_id=uuid.uuid4(),
                tipo="Parcial", numero=1, periodo="2025-1",
                fecha=date(2025, 5, 15), titulo="1P",
                extra="boom",
            )
            assert False
        except ValidationError:
            pass
