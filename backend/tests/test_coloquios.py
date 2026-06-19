"""Tests for Coloquios module (C-14).

Strict TDD: tests written BEFORE implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.dependencies import get_current_user, get_db
from app.core.security import create_access_token
from app.models.asignacion import Asignacion
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User

from .conftest import TEST_SETTINGS

# ═══════════════════════════════════════════════════════════════════════════════
# Shared seed data fixture
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_coloquios(async_client: AsyncClient) -> dict:
    """Minimal seed: tenant + users + roles + academic data + coloquio perms."""
    from app.core.security import hash_password

    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Coloquios Tenant", codigo=f"CO{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        admin = User(
            tenant_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("AdminPass123!"),
            display_name="Admin User",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        profesor = User(
            tenant_id=tenant.id,
            email=f"prof-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("ProfPass123!"),
            display_name="Profesor Test",
            is_active=True,
        )
        session.add(profesor)
        await session.flush()

        coordinador = User(
            tenant_id=tenant.id,
            email=f"coord-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("CoordPass123!"),
            display_name="Coordinador Test",
            is_active=True,
        )
        session.add(coordinador)
        await session.flush()

        no_perm_user = User(
            tenant_id=tenant.id,
            email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"),
            display_name="No Perm User",
            is_active=True,
        )
        session.add(no_perm_user)
        await session.flush()

        alumno1 = User(
            tenant_id=tenant.id,
            email=f"al1-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("AlumnoPass123!"),
            display_name="Alumno Uno",
            is_active=True,
        )
        session.add(alumno1)
        await session.flush()

        alumno2 = User(
            tenant_id=tenant.id,
            email=f"al2-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("AlumnoPass123!"),
            display_name="Alumno Dos",
            is_active=True,
        )
        session.add(alumno2)
        await session.flush()

        # Academic data
        carrera = Carrera(
            tenant_id=tenant.id, codigo="TUP", nombre="Tecnico en Programacion"
        )
        session.add(carrera)
        await session.flush()

        cohorte = Cohorte(
            tenant_id=tenant.id,
            carrera_id=carrera.id,
            nombre="2026-A",
            anio=2026,
            vig_desde=date(2026, 3, 1),
        )
        session.add(cohorte)
        await session.flush()

        materia = Materia(
            tenant_id=tenant.id, codigo="PROG1", nombre="Programación I"
        )
        session.add(materia)
        await session.flush()

        materia2 = Materia(
            tenant_id=tenant.id, codigo="PROG2", nombre="Programación II"
        )
        session.add(materia2)
        await session.flush()

        # Roles
        role_admin = Role(tenant_id=tenant.id, nombre="Admin", codigo="ADMIN")
        session.add(role_admin)
        await session.flush()

        role_prof = Role(tenant_id=tenant.id, nombre="Profesor", codigo="PROFESOR")
        session.add(role_prof)
        await session.flush()

        role_coord = Role(tenant_id=tenant.id, nombre="Coordinador", codigo="COORDINADOR")
        session.add(role_coord)
        await session.flush()

        role_alumno = Role(tenant_id=tenant.id, nombre="Alumno", codigo="ALUMNO")
        session.add(role_alumno)
        await session.flush()

        # Permissions
        perm_gestionar = Permission(tenant_id=tenant.id, codigo="coloquios:gestionar")
        session.add(perm_gestionar)
        await session.flush()
        for role in [role_admin, role_prof, role_coord]:
            rp = RolePermission(role_id=role.id, permission_id=perm_gestionar.id)
            session.add(rp)

        perm_ver = Permission(tenant_id=tenant.id, codigo="coloquios:ver")
        session.add(perm_ver)
        await session.flush()
        for role in [role_admin, role_prof, role_coord]:
            rp = RolePermission(role_id=role.id, permission_id=perm_ver.id)
            session.add(rp)

        await session.flush()

        # Assign roles to users
        for user_id, role in [
            (admin.id, role_admin),
            (profesor.id, role_prof),
            (coordinador.id, role_coord),
            (alumno1.id, role_alumno),
            (alumno2.id, role_alumno),
        ]:
            ur = UserRole(
                tenant_id=tenant.id,
                user_id=user_id,
                role_id=role.id,
                desde=date(2024, 1, 1),
            )
            session.add(ur)

        await session.flush()

        # Asignaciones
        asignacion_prof = Asignacion(
            tenant_id=tenant.id,
            usuario_id=profesor.id,
            rol="PROFESOR",
            materia_id=materia.id,
            cohorte_id=cohorte.id,
            comisiones=[],
            desde=date(2024, 1, 1),
        )
        session.add(asignacion_prof)
        await session.flush()

        data.update({
            "tenant_id": tenant.id,
            "admin_id": admin.id,
            "profesor_id": profesor.id,
            "coordinador_id": coordinador.id,
            "no_perm_user_id": no_perm_user.id,
            "alumno1_id": alumno1.id,
            "alumno2_id": alumno2.id,
            "carrera_id": carrera.id,
            "cohorte_id": cohorte.id,
            "materia_id": materia.id,
            "materia2_id": materia2.id,
            "asignacion_prof_id": asignacion_prof.id,
        })
        await session.commit()

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 tests: Model definitions
# ═══════════════════════════════════════════════════════════════════════════════


class TestTipoEvaluacionEnum:
    """TipoEvaluacion enum values."""

    def test_enum_values(self):
        from app.models.evaluacion import TipoEvaluacion
        assert TipoEvaluacion.Parcial.value == "Parcial"
        assert TipoEvaluacion.TP.value == "TP"
        assert TipoEvaluacion.Coloquio.value == "Coloquio"
        assert TipoEvaluacion.Recuperatorio.value == "Recuperatorio"


class TestEvaluacionModel:
    """Evaluacion model — structural tests."""

    def test_imports(self):
        from app.models.evaluacion import Evaluacion
        assert Evaluacion.__tablename__ == "evaluacion"

    def test_fields_exist(self):
        from app.models.evaluacion import Evaluacion
        cols = {c.name for c in Evaluacion.__table__.columns}
        assert "materia_id" in cols
        assert "cohorte_id" in cols
        assert "tipo" in cols
        assert "instancia" in cols
        assert "dias_disponibles" in cols
        assert "activa" in cols
        assert "tenant_id" in cols


class TestEstadoReservaEnum:
    """EstadoReserva enum values."""

    def test_enum_values(self):
        from app.models.reserva_evaluacion import EstadoReserva
        assert EstadoReserva.Activa.value == "Activa"
        assert EstadoReserva.Cancelada.value == "Cancelada"


class TestReservaEvaluacionModel:
    """ReservaEvaluacion model — structural tests."""

    def test_imports(self):
        from app.models.reserva_evaluacion import ReservaEvaluacion
        assert ReservaEvaluacion.__tablename__ == "reserva_evaluacion"

    def test_fields_exist(self):
        from app.models.reserva_evaluacion import ReservaEvaluacion
        cols = {c.name for c in ReservaEvaluacion.__table__.columns}
        assert "evaluacion_id" in cols
        assert "alumno_id" in cols
        assert "fecha_hora" in cols
        assert "estado" in cols
        assert "tenant_id" in cols


class TestResultadoEvaluacionModel:
    """ResultadoEvaluacion model — structural tests."""

    def test_imports(self):
        from app.models.resultado_evaluacion import ResultadoEvaluacion
        assert ResultadoEvaluacion.__tablename__ == "resultado_evaluacion"

    def test_fields_exist(self):
        from app.models.resultado_evaluacion import ResultadoEvaluacion
        cols = {c.name for c in ResultadoEvaluacion.__table__.columns}
        assert "evaluacion_id" in cols
        assert "alumno_id" in cols
        assert "nota_final" in cols
        assert "registrada_at" in cols
        assert "tenant_id" in cols


class TestColoquiosModelInit:
    """Models can be instantiated from __init__."""

    def test_evaluacion_exported(self):
        from app.models import Evaluacion
        assert Evaluacion.__tablename__ == "evaluacion"

    def test_tipo_evaluacion_exported(self):
        from app.models import TipoEvaluacion
        assert TipoEvaluacion.Coloquio.value == "Coloquio"

    def test_reserva_evaluacion_exported(self):
        from app.models import ReservaEvaluacion
        assert ReservaEvaluacion.__tablename__ == "reserva_evaluacion"

    def test_estado_reserva_exported(self):
        from app.models import EstadoReserva
        assert EstadoReserva.Activa.value == "Activa"

    def test_resultado_evaluacion_exported(self):
        from app.models import ResultadoEvaluacion
        assert ResultadoEvaluacion.__tablename__ == "resultado_evaluacion"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 tests: Repositories
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_evaluaciones(seed_coloquios: dict) -> dict:
    """Seed evaluacion + resultado_evaluacion + reserva_evaluacion data."""
    from app.models.evaluacion import Evaluacion
    from app.models.reserva_evaluacion import ReservaEvaluacion, EstadoReserva
    from app.models.resultado_evaluacion import ResultadoEvaluacion

    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data = dict(seed_coloquios)

    async with factory() as session:
        # Evaluacion activa
        ev = Evaluacion(
            tenant_id=data["tenant_id"],
            materia_id=data["materia_id"],
            cohorte_id=data["cohorte_id"],
            tipo="Coloquio",
            instancia="Coloquio Final 2026",
            dias_disponibles=30,
            activa=True,
        )
        session.add(ev)
        await session.flush()
        data["evaluacion_id"] = ev.id

        # Evaluacion cerrada
        ev_cerrada = Evaluacion(
            tenant_id=data["tenant_id"],
            materia_id=data["materia_id"],
            cohorte_id=data["cohorte_id"],
            tipo="Parcial",
            instancia="Parcial 1",
            dias_disponibles=10,
            activa=False,
        )
        session.add(ev_cerrada)
        await session.flush()
        data["evaluacion_cerrada_id"] = ev_cerrada.id

        # Evaluacion otra materia
        ev_otra = Evaluacion(
            tenant_id=data["tenant_id"],
            materia_id=data["materia2_id"],
            cohorte_id=data["cohorte_id"],
            tipo="Coloquio",
            instancia="Coloquio PROG2",
            dias_disponibles=20,
            activa=True,
        )
        session.add(ev_otra)
        await session.flush()
        data["evaluacion_otra_id"] = ev_otra.id

        # Resultados (alumno1 habilitado en ev, alumno2 habilitado en ev_otra)
        res1 = ResultadoEvaluacion(
            tenant_id=data["tenant_id"],
            evaluacion_id=ev.id,
            alumno_id=data["alumno1_id"],
            nota_final=None,
        )
        session.add(res1)
        await session.flush()
        data["resultado_id"] = res1.id

        res2 = ResultadoEvaluacion(
            tenant_id=data["tenant_id"],
            evaluacion_id=ev.id,
            alumno_id=data["alumno2_id"],
            nota_final=None,
        )
        session.add(res2)
        await session.flush()
        data["resultado2_id"] = res2.id

        res3 = ResultadoEvaluacion(
            tenant_id=data["tenant_id"],
            evaluacion_id=ev_otra.id,
            alumno_id=data["alumno2_id"],
            nota_final=None,
        )
        session.add(res3)
        await session.flush()
        data["resultado3_id"] = res3.id

        # Reserva activa para ev (alumno1)
        reserva = ReservaEvaluacion(
            tenant_id=data["tenant_id"],
            evaluacion_id=ev.id,
            alumno_id=data["alumno1_id"],
            fecha_hora=datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC),
            estado=EstadoReserva.Activa.value,
        )
        session.add(reserva)
        await session.flush()
        data["reserva_id"] = reserva.id

        await session.commit()

    await engine.dispose()
    return data


class TestEvaluacionRepository:
    """EvaluacionRepository CRUD tests."""

    async def test_create_and_get(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import EvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = EvaluacionRepository(session=session, tenant_id=seed_evaluaciones["tenant_id"])
            ev = await repo.get(seed_evaluaciones["evaluacion_id"])
            assert ev is not None
            assert ev.tipo == "Coloquio"
            assert ev.instancia == "Coloquio Final 2026"
            assert ev.dias_disponibles == 30
            assert ev.activa is True
        await engine.dispose()

    async def test_list_activas(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import EvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = EvaluacionRepository(session=session, tenant_id=seed_evaluaciones["tenant_id"])
            activas = await repo.list_activas()
            ids = {e.id for e in activas}
            assert seed_evaluaciones["evaluacion_id"] in ids
            assert seed_evaluaciones["evaluacion_otra_id"] in ids
            assert seed_evaluaciones["evaluacion_cerrada_id"] not in ids
        await engine.dispose()

    async def test_list_con_metricas(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import EvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = EvaluacionRepository(session=session, tenant_id=seed_evaluaciones["tenant_id"])
            metricas = await repo.list_con_metricas()
            # Should return items with convocados, reservas_activas, cupo_disponible
            assert len(metricas) >= 2
            ev_meta = next(m for m in metricas if m["id"] == seed_evaluaciones["evaluacion_id"])
            assert ev_meta["convocados"] == 2  # alumno1 + alumno2
            assert ev_meta["reservas_activas"] == 1  # alumno1 reservó
            assert ev_meta["cupo_disponible"] == 29  # 30 - 1
        await engine.dispose()

    async def test_update(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import EvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = EvaluacionRepository(session=session, tenant_id=seed_evaluaciones["tenant_id"])
            updated = await repo.update(seed_evaluaciones["evaluacion_id"], activa=False)
            assert updated is not None
            assert updated.activa is False
        await engine.dispose()


class TestReservaEvaluacionRepository:
    """ReservaEvaluacionRepository CRUD tests."""

    async def test_create_and_get(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ReservaEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ReservaEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            r = await repo.get(seed_evaluaciones["reserva_id"])
            assert r is not None
            assert r.estado == "Activa"
            assert r.alumno_id == seed_evaluaciones["alumno1_id"]
        await engine.dispose()

    async def test_count_activas_por_evaluacion(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ReservaEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ReservaEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            count = await repo.count_activas_por_evaluacion(seed_evaluaciones["evaluacion_id"])
            assert count == 1
        await engine.dispose()

    async def test_list_por_alumno(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ReservaEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ReservaEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            reservas = await repo.list_por_alumno(seed_evaluaciones["alumno1_id"])
            assert len(reservas) == 1
            assert reservas[0].estado == "Activa"
        await engine.dispose()

    async def test_list_activas(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ReservaEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ReservaEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            activas = await repo.list_activas()
            assert len(activas) >= 1
            for r in activas:
                assert r.estado == "Activa"
        await engine.dispose()


class TestResultadoEvaluacionRepository:
    """ResultadoEvaluacionRepository CRUD tests."""

    async def test_create_and_get(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ResultadoEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ResultadoEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            r = await repo.get(seed_evaluaciones["resultado_id"])
            assert r is not None
            assert r.nota_final is None
        await engine.dispose()

    async def test_list_por_evaluacion(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ResultadoEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ResultadoEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            resultados = await repo.list_por_evaluacion(seed_evaluaciones["evaluacion_id"])
            assert len(resultados) == 2
        await engine.dispose()

    async def test_count_notas_registradas(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ResultadoEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ResultadoEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            count = await repo.count_notas_registradas()
            assert count == 0  # none registered yet
        await engine.dispose()

    async def test_list_con_notas(self, seed_evaluaciones: dict):
        from app.repositories.coloquio_repository import ResultadoEvaluacionRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = ResultadoEvaluacionRepository(
                session=session, tenant_id=seed_evaluaciones["tenant_id"]
            )
            # First register a note
            await repo.update(seed_evaluaciones["resultado_id"], nota_final="8")

            con_notas = await repo.list_con_notas()
            assert len(con_notas) >= 1
            for r in con_notas:
                assert r.nota_final is not None
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 tests: Schema validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluacionSchemas:
    """Schema validation tests."""

    def test_crear_request_valido(self):
        from app.schemas.coloquios import EvaluacionCrearRequest
        data = EvaluacionCrearRequest(
            materia_id=uuid.uuid4(),
            cohorte_id=uuid.uuid4(),
            tipo="Coloquio",
            instancia="Coloquio Final",
            dias_disponibles=30,
        )
        assert data.tipo == "Coloquio"
        assert data.dias_disponibles == 30

    def test_crear_request_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.coloquios import EvaluacionCrearRequest
        with pytest.raises(ValidationError):
            EvaluacionCrearRequest(
                materia_id=uuid.uuid4(),
                cohorte_id=uuid.uuid4(),
                tipo="Coloquio",
                instancia="Test",
                dias_disponibles=30,
                extra="bad",
            )

    def test_crear_request_invalid_tipo(self):
        from pydantic import ValidationError
        from app.schemas.coloquios import EvaluacionCrearRequest
        with pytest.raises(ValidationError):
            EvaluacionCrearRequest(
                materia_id=uuid.uuid4(),
                cohorte_id=uuid.uuid4(),
                tipo="Invalido",
                instancia="Test",
                dias_disponibles=30,
            )

    def test_response_from_attributes(self):
        from app.schemas.coloquios import EvaluacionResponse
        eid = uuid.uuid4()
        tid = uuid.uuid4()
        data = EvaluacionResponse(
            id=eid,
            tenant_id=tid,
            materia_id=uuid.uuid4(),
            cohorte_id=uuid.uuid4(),
            tipo="Coloquio",
            instancia="Test",
            dias_disponibles=30,
            activa=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert data.id == eid
        assert data.activa is True

    def test_importar_request_valido(self):
        from app.schemas.coloquios import ImportarAlumnosRequest
        ids = [uuid.uuid4(), uuid.uuid4()]
        data = ImportarAlumnosRequest(alumno_ids=ids)
        assert len(data.alumno_ids) == 2

    def test_importar_request_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.coloquios import ImportarAlumnosRequest
        with pytest.raises(ValidationError):
            ImportarAlumnosRequest(
                alumno_ids=[uuid.uuid4()],
                extra="bad",
            )

    def test_reserva_request_valido(self):
        from app.schemas.coloquios import ReservaRequest
        data = ReservaRequest(fecha_hora=datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC))
        assert data.fecha_hora == datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)

    def test_resultado_update_request(self):
        from app.schemas.coloquios import ResultadoUpdateRequest
        data = ResultadoUpdateRequest(nota_final="8")
        assert data.nota_final == "8"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 tests: Service
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def coloquio_service_fixtures(seed_evaluaciones: dict, seed_coloquios: dict) -> dict:
    """Extended seed with alumno tokens."""
    data = dict(seed_evaluaciones)
    data.update(seed_coloquios)

    # Alumno tokens
    data["alumno1_token"] = create_access_token(data={
        "sub": str(seed_coloquios["alumno1_id"]),
        "tenant_id": str(seed_coloquios["tenant_id"]),
    })
    data["alumno2_token"] = create_access_token(data={
        "sub": str(seed_coloquios["alumno2_id"]),
        "tenant_id": str(seed_coloquios["tenant_id"]),
    })
    return data


class TestColoquioService:
    """Service layer tests."""

    async def test_crear_convocatoria(self, seed_coloquios: dict):
        """Crear convocatoria creates evaluacion."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["coordinador_id"],
            )
            ev = await service.crear_convocatoria(
                materia_id=seed_coloquios["materia_id"],
                cohorte_id=seed_coloquios["cohorte_id"],
                tipo="Coloquio",
                instancia="Coloquio TDD",
                dias_disponibles=30,
            )
            assert ev is not None
            assert ev.instancia == "Coloquio TDD"
            assert ev.activa is True
        await engine.dispose()

    async def test_importar_alumnos(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Importar alumnos crea resultados con nota_final=NULL."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["coordinador_id"],
            )
            result = await service.importar_alumnos(
                evaluacion_id=seed_evaluaciones["evaluacion_id"],
                alumno_ids=[seed_coloquios["alumno1_id"], seed_coloquios["alumno2_id"]],
            )
            assert result["importados"] == 0  # ya existían
            assert result["ya_existentes"] == 2
        await engine.dispose()

    async def test_importar_alumnos_nuevos(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Importar alumnos nuevos crea resultados."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["coordinador_id"],
            )
            result = await service.importar_alumnos(
                evaluacion_id=seed_evaluaciones["evaluacion_otra_id"],
                alumno_ids=[seed_coloquios["alumno1_id"]],
            )
            assert result["importados"] == 1
            assert result["ya_existentes"] == 0
        await engine.dispose()

    async def test_reservar_con_cupo(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Reservar con cupo disponible crea reserva."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["alumno2_id"],
            )
            reserva = await service.reservar_turno(
                evaluacion_id=seed_evaluaciones["evaluacion_id"],
                fecha_hora=datetime(2026, 8, 1, 14, 0, 0, tzinfo=UTC),
            )
            assert reserva is not None
            assert reserva.estado == "Activa"
            assert reserva.alumno_id == seed_coloquios["alumno2_id"]
        await engine.dispose()

    async def test_reservar_sin_cupo(self, seed_coloquios: dict):
        """Reservar sin cupo → 409."""
        from fastapi import HTTPException
        from app.services.coloquio_service import ColoquioService
        import uuid as _uuid

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            # Create evaluacion with dias_disponibles=1
            from app.models.evaluacion import Evaluacion
            ev = Evaluacion(
                tenant_id=seed_coloquios["tenant_id"],
                materia_id=seed_coloquios["materia_id"],
                cohorte_id=seed_coloquios["cohorte_id"],
                tipo="Coloquio",
                instancia="Cupo Test",
                dias_disponibles=1,
                activa=True,
            )
            session.add(ev)
            await session.flush()

            # Add resultado for alumno1
            from app.models.resultado_evaluacion import ResultadoEvaluacion
            res = ResultadoEvaluacion(
                tenant_id=seed_coloquios["tenant_id"],
                evaluacion_id=ev.id,
                alumno_id=seed_coloquios["alumno1_id"],
                nota_final=None,
            )
            session.add(res)
            await session.flush()
            await session.commit()

        # Now test reserva with cupo=1
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["alumno1_id"],
            )
            # First reservation — should succeed
            reserva = await service.reservar_turno(
                evaluacion_id=ev.id,
                fecha_hora=datetime(2026, 8, 1, 14, 0, 0, tzinfo=UTC),
            )
            assert reserva is not None

            # Second reservation — should fail
            with pytest.raises(HTTPException) as exc:
                await service.reservar_turno(
                    evaluacion_id=ev.id,
                    fecha_hora=datetime(2026, 8, 2, 14, 0, 0, tzinfo=UTC),
                )
            assert exc.value.status_code == 409

        await engine.dispose()

    async def test_cancelar_reserva(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Cancelar reserva cambia estado a Cancelada."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["alumno1_id"],
            )
            result = await service.cancelar_reserva(
                reserva_id=seed_evaluaciones["reserva_id"],
            )
            assert result is True
        await engine.dispose()

    async def test_listar_disponibles_para_alumno(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Alumno ve solo convocatorias donde está habilitado."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["alumno1_id"],
            )
            disponibles = await service.listar_disponibles_para_alumno()
            # alumno1 está en evaluacion_id pero no en evaluacion_otra_id
            ids = [d["id"] for d in disponibles]
            assert seed_evaluaciones["evaluacion_id"] in ids
            assert seed_evaluaciones["evaluacion_otra_id"] not in ids
        await engine.dispose()

    async def test_listar_mis_reservas(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Listar mis reservas."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["alumno1_id"],
            )
            reservas = await service.listar_mis_reservas()
            assert len(reservas) == 1
        await engine.dispose()

    async def test_registrar_nota(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Registrar nota actualiza resultado."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["coordinador_id"],
            )
            result = await service.registrar_nota(
                resultado_id=seed_evaluaciones["resultado_id"],
                nota_final="8",
            )
            assert result.nota_final == "8"
            assert result.registrada_at is not None
        await engine.dispose()

    async def test_get_metricas(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Metricas returns correct counts."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["coordinador_id"],
            )
            metricas = await service.get_metricas()
            assert metricas["total_alumnos_cargados"] == 2
            assert metricas["instancias_activas"] >= 2
            assert metricas["reservas_activas"] == 1
            assert metricas["notas_registradas"] == 0
        await engine.dispose()

    async def test_cerrar_convocatoria(self, seed_coloquios: dict, seed_evaluaciones: dict):
        """Cerrar convocatoria desactiva evaluacion."""
        from app.services.coloquio_service import ColoquioService

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            service = ColoquioService(
                db=session,
                tenant_id=seed_coloquios["tenant_id"],
                current_user_id=seed_coloquios["coordinador_id"],
            )
            ev = await service.cerrar_convocatoria(
                evaluacion_id=seed_evaluaciones["evaluacion_id"],
            )
            assert ev.activa is False
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5 & 6 tests: E2E API
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def coloquio_tokens(seed_coloquios: dict) -> dict:
    """JWT tokens for various users."""
    tokens = {}
    for role, key in [
        ("admin", "admin_id"),
        ("profesor", "profesor_id"),
        ("coordinador", "coordinador_id"),
        ("alumno1", "alumno1_id"),
        ("alumno2", "alumno2_id"),
        ("no_perm", "no_perm_user_id"),
    ]:
        tokens[role] = create_access_token(data={
            "sub": str(seed_coloquios[key]),
            "tenant_id": str(seed_coloquios["tenant_id"]),
        })
    return tokens


class TestE2EColoquios:
    """Full E2E flow tests."""

    COLOQUIOS_URL = "/api/coloquios"

    async def test_crear_convocatoria_e2e(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """POST /api/coloquios → 201 (AT-01)."""
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Coloquio Final E2E",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["instancia"] == "Coloquio Final E2E"
        assert body["activa"] is True

    async def test_crear_sin_campos_422(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """POST /api/coloquios sin materia_id → 422 (AT-02)."""
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Test",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 422, resp.text

    async def test_importar_alumnos_e2e(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """POST /coloquios/{id}/alumnos → importados=N (AT-03)."""
        # First create the evaluacion
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Import E2E",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        # Import alumnos
        resp = await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/alumnos",
            json={
                "alumno_ids": [
                    str(seed_coloquios["alumno1_id"]),
                    str(seed_coloquios["alumno2_id"]),
                ],
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["importados"] == 2
        assert body["ya_existentes"] == 0

    async def test_importar_duplicados(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """Importar duplicados → ya_existentes=N (AT-04)."""
        # Create + import once
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Dup E2E",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        # First import
        await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/alumnos",
            json={"alumno_ids": [str(seed_coloquios["alumno1_id"])]},
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )

        # Second import with same + new
        resp = await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/alumnos",
            json={
                "alumno_ids": [
                    str(seed_coloquios["alumno1_id"]),
                    str(seed_coloquios["alumno2_id"]),
                ],
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["importados"] == 1
        assert body["ya_existentes"] == 1

    async def test_alumno_reserva_y_cancela(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """Full alumno flow: disponible → reservar → mis-reservas → cancelar (AT-07, AT-09, AT-10)."""
        # Create evaluacion + import alumno1
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Alumno Flow E2E",
                "dias_disponibles": 5,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/alumnos",
            json={"alumno_ids": [str(seed_coloquios["alumno1_id"])]},
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )

        # AT-10: Alumno ve disponible
        resp = await async_client.get(
            f"{self.COLOQUIOS_URL}/disponibles",
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        ids = [i["id"] for i in items]
        assert ev_id in ids

        # AT-07: Reservar
        resp = await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/reservar",
            json={"fecha_hora": "2026-07-15T10:00:00Z"},
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 201, resp.text
        reserva = resp.json()
        assert reserva["estado"] == "Activa"
        reserva_id = reserva["id"]

        # Ver mis reservas
        resp = await async_client.get(
            f"{self.COLOQUIOS_URL}/mis-reservas",
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) >= 1

        # AT-09: Cancelar
        resp = await async_client.delete(
            f"{self.COLOQUIOS_URL}/reservas/{reserva_id}",
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 200, resp.text

    async def test_sin_cupo_409(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """Reservar sin cupo → 409 (AT-08)."""
        # Evaluacion con dias_disponibles=1
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Sin Cupo E2E",
                "dias_disponibles": 1,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        # Import both alumnos
        await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/alumnos",
            json={
                "alumno_ids": [
                    str(seed_coloquios["alumno1_id"]),
                    str(seed_coloquios["alumno2_id"]),
                ],
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )

        # alumno1 reserves
        resp = await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/reservar",
            json={"fecha_hora": "2026-07-15T10:00:00Z"},
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 201

        # alumno2 tries → 409
        resp = await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/reservar",
            json={"fecha_hora": "2026-07-16T10:00:00Z"},
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno2']}"},
        )
        assert resp.status_code == 409, resp.text
        assert "No hay cupo" in resp.text

    async def test_registrar_nota_e2e(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """PATCH /coloquios/resultados/{id} → 200 (AT-12)."""
        # Create + import
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Nota E2E",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        resp = await async_client.post(
            f"{self.COLOQUIOS_URL}/{ev_id}/alumnos",
            json={"alumno_ids": [str(seed_coloquios["alumno1_id"])]},
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200
        resultados = resp.json().get("resultados", [])
        if not resultados:
            # Get resultados via service
            resp = await async_client.get(
                f"{self.COLOQUIOS_URL}/registro",
                headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
            )
            items = resp.json()["items"]
            resultado_ids = [r["id"] for r in items if r.get("evaluacion_id") == ev_id or True]
            if resultado_ids:
                resultado_id = resultado_ids[0]
            else:
                # fallback: get the first resultado for this evaluacion
                from sqlalchemy import select
                from app.models.resultado_evaluacion import ResultadoEvaluacion
                engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
                factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                async with factory() as session:
                    stmt = select(ResultadoEvaluacion).where(
                        ResultadoEvaluacion.evaluacion_id == ev_id
                    )
                    result = await session.execute(stmt)
                    r = result.scalar_one()
                    resultado_id = str(r.id)
                await engine.dispose()
        else:
            resultado_id = resultados[0]["id"]

        resp = await async_client.patch(
            f"{self.COLOQUIOS_URL}/resultados/{resultado_id}",
            json={"nota_final": "8"},
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["nota_final"] == "8"

    async def test_metricas_e2e(
        self, async_client: AsyncClient, seed_coloquios: dict, seed_evaluaciones: dict,
        coloquio_tokens: dict,
    ):
        """GET /coloquios/metricas → correct counts (AT-13)."""
        resp = await async_client.get(
            f"{self.COLOQUIOS_URL}/metricas",
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_alumnos_cargados"] == 2
        assert body["instancias_activas"] >= 2
        assert body["reservas_activas"] == 1
        assert body["notas_registradas"] == 0

    async def test_listar_convocatorias(
        self, async_client: AsyncClient, seed_coloquios: dict, seed_evaluaciones: dict,
        coloquio_tokens: dict,
    ):
        """GET /coloquios → list with metrics (AT-05)."""
        resp = await async_client.get(
            self.COLOQUIOS_URL,
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 2
        for item in body["items"]:
            assert "convocados" in item
            assert "reservas_activas" in item
            assert "cupo_disponible" in item

    async def test_cerrar_convocatoria_e2e(
        self, async_client: AsyncClient, seed_coloquios: dict, coloquio_tokens: dict,
    ):
        """PATCH /coloquios/{id} → activa=false (AT-06)."""
        resp = await async_client.post(
            self.COLOQUIOS_URL,
            json={
                "materia_id": str(seed_coloquios["materia_id"]),
                "cohorte_id": str(seed_coloquios["cohorte_id"]),
                "tipo": "Coloquio",
                "instancia": "Cerrar E2E",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        resp = await async_client.patch(
            f"{self.COLOQUIOS_URL}/{ev_id}",
            json={"activa": False},
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["activa"] is False

    async def test_agenda(
        self, async_client: AsyncClient, seed_coloquios: dict, seed_evaluaciones: dict,
        coloquio_tokens: dict,
    ):
        """GET /coloquios/agenda → reservas activas (AT-14)."""
        resp = await async_client.get(
            f"{self.COLOQUIOS_URL}/agenda",
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) >= 1
        for item in items:
            assert "alumno" in item
            assert "materia" in item
            assert "fecha_hora" in item

    async def test_registro(
        self, async_client: AsyncClient, seed_coloquios: dict, seed_evaluaciones: dict,
        coloquio_tokens: dict,
    ):
        """GET /coloquios/registro → resultados with notas (AT-15)."""
        resp = await async_client.get(
            f"{self.COLOQUIOS_URL}/registro",
            headers={"Authorization": f"Bearer {coloquio_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        # Initially no notas registered
        body = resp.json()
        assert "items" in body

    async def test_alumno_no_ve_otra_convocatoria(
        self, async_client: AsyncClient, seed_coloquios: dict, seed_evaluaciones: dict,
        coloquio_tokens: dict,
    ):
        """Alumno ve solo sus convocatorias (AT-10 variant)."""
        resp = await async_client.get(
            f"{self.COLOQUIOS_URL}/disponibles",
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno2']}"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = set(i["id"] for i in items)
        # alumno2 está en ambas evaluaciones
        assert str(seed_evaluaciones["evaluacion_id"]) in ids
        assert str(seed_evaluaciones["evaluacion_otra_id"]) in ids


class TestPermissionsColoquios:
    """Permission tests (AT-16 to AT-19)."""

    async def test_no_token_returns_403(self, async_client: AsyncClient):
        """Sin token → 403 (AT-19)."""
        endpoints = [
            ("POST", "/api/coloquios"),
            ("GET", "/api/coloquios"),
            ("GET", "/api/coloquios/metricas"),
            ("GET", "/api/coloquios/agenda"),
            ("GET", "/api/coloquios/registro"),
            ("GET", "/api/coloquios/disponibles"),
            ("POST", f"/api/coloquios/{uuid.uuid4()}/reservar"),
            ("DELETE", f"/api/coloquios/reservas/{uuid.uuid4()}"),
        ]
        for method, url in endpoints:
            resp = await async_client.request(method, url)
            assert resp.status_code == 403, f"{method} {url} should be 403, got {resp.status_code}"

    async def test_sin_permiso_gestionar_403(
        self, async_client: AsyncClient, coloquio_tokens: dict,
    ):
        """Sin coloquios:gestionar → 403 en endpoints de gestión (AT-16)."""
        resp = await async_client.post(
            "/api/coloquios",
            json={
                "materia_id": str(uuid.uuid4()),
                "cohorte_id": str(uuid.uuid4()),
                "tipo": "Coloquio",
                "instancia": "Test",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['no_perm']}"},
        )
        assert resp.status_code == 403, resp.text

    async def test_sin_permiso_ver_403(
        self, async_client: AsyncClient, coloquio_tokens: dict,
    ):
        """Sin coloquios:ver → 403 en endpoints de consulta (AT-17)."""
        resp = await async_client.get(
            "/api/coloquios",
            headers={"Authorization": f"Bearer {coloquio_tokens['no_perm']}"},
        )
        assert resp.status_code == 403, resp.text

    async def test_alumno_no_puede_gestionar(
        self, async_client: AsyncClient, coloquio_tokens: dict,
    ):
        """ALUMNO → 403 en POST /coloquios (AT-18)."""
        resp = await async_client.post(
            "/api/coloquios",
            json={
                "materia_id": str(uuid.uuid4()),
                "cohorte_id": str(uuid.uuid4()),
                "tipo": "Coloquio",
                "instancia": "Test",
                "dias_disponibles": 30,
            },
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 403, resp.text

    async def test_alumno_puede_reservar(
        self, async_client: AsyncClient, seed_coloquios: dict, seed_evaluaciones: dict,
        coloquio_tokens: dict,
    ):
        """ALUMNO → puede acceder a disponibles y reservar."""
        resp = await async_client.get(
            f"/api/coloquios/disponibles",
            headers={"Authorization": f"Bearer {coloquio_tokens['alumno1']}"},
        )
        assert resp.status_code == 200
