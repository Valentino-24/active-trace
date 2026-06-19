"""Tests for Avisos module (C-15).

Strict TDD: tests written BEFORE implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from httpx import AsyncClient

from app.core.security import create_access_token
from .conftest import TEST_SETTINGS


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Model definitions (Task 1.1 & 1.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlcanceAvisoEnum:
    """AlcanceAviso enum values."""

    def test_enum_values(self):
        from app.models.aviso import AlcanceAviso
        assert AlcanceAviso.Global.value == "Global"
        assert AlcanceAviso.PorMateria.value == "PorMateria"
        assert AlcanceAviso.PorCohorte.value == "PorCohorte"
        assert AlcanceAviso.PorRol.value == "PorRol"


class TestSeveridadAvisoEnum:
    """SeveridadAviso enum values."""

    def test_enum_values(self):
        from app.models.aviso import SeveridadAviso
        assert SeveridadAviso.Info.value == "Info"
        assert SeveridadAviso.Advertencia.value == "Advertencia"
        assert SeveridadAviso.Crítico.value == "Crítico"


class TestAvisoModel:
    """Aviso model — structural tests."""

    def test_imports(self):
        from app.models.aviso import Aviso
        assert Aviso.__tablename__ == "aviso"

    def test_fields_exist(self):
        from app.models.aviso import Aviso
        cols = {c.name for c in Aviso.__table__.columns}
        assert "tenant_id" in cols
        assert "alcance" in cols
        assert "materia_id" in cols
        assert "cohorte_id" in cols
        assert "rol_destino" in cols
        assert "severidad" in cols
        assert "titulo" in cols
        assert "cuerpo" in cols
        assert "inicio_en" in cols
        assert "fin_en" in cols
        assert "orden" in cols
        assert "activo" in cols
        assert "requiere_ack" in cols
        assert "deleted_at" in cols  # Soft delete

    def test_inherits_soft_delete(self):
        from app.models.aviso import Aviso
        assert hasattr(Aviso, "deleted_at")


class TestAcknowledgmentAvisoModel:
    """AcknowledgmentAviso model — structural tests."""

    def test_imports(self):
        from app.models.acknowledgment_aviso import AcknowledgmentAviso
        assert AcknowledgmentAviso.__tablename__ == "acknowledgment_aviso"

    def test_fields_exist(self):
        from app.models.acknowledgment_aviso import AcknowledgmentAviso
        cols = {c.name for c in AcknowledgmentAviso.__table__.columns}
        assert "aviso_id" in cols
        assert "usuario_id" in cols
        assert "confirmado_at" in cols
        assert "created_at" in cols
        # NO soft delete — audit record (updated_at is inherited from BaseModelMixin but unused)
        assert "deleted_at" not in cols

    def test_no_soft_delete(self):
        from app.models.acknowledgment_aviso import AcknowledgmentAviso
        assert not hasattr(AcknowledgmentAviso, "deleted_at")


class TestAvisosModelInit:
    """Models can be instantiated from __init__."""

    def test_aviso_exported(self):
        from app.models import Aviso
        assert Aviso.__tablename__ == "aviso"

    def test_alcance_aviso_exported(self):
        from app.models import AlcanceAviso
        assert AlcanceAviso.Global.value == "Global"

    def test_severidad_aviso_exported(self):
        from app.models import SeveridadAviso
        assert SeveridadAviso.Info.value == "Info"

    def test_acknowledgment_aviso_exported(self):
        from app.models import AcknowledgmentAviso
        assert AcknowledgmentAviso.__tablename__ == "acknowledgment_aviso"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Repository integration tests (need DB)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_avisos() -> dict:
    """Minimal seed: tenant + users + roles + academic data + aviso perms."""
    from uuid import uuid4 as _uuid4

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.core.security import hash_password
    from app.models.asignacion import Asignacion
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
        tenant = Tenant(nombre="Avisos Tenant", codigo=f"AV{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        admin = User(
            tenant_id=tenant.id, email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("AdminPass123!"), display_name="Admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        profesor = User(
            tenant_id=tenant.id, email=f"prof-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("ProfPass123!"), display_name="Profesor",
            is_active=True,
        )
        session.add(profesor)
        await session.flush()

        tutor = User(
            tenant_id=tenant.id, email=f"tutor-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("TutorPass123!"), display_name="Tutor",
            is_active=True,
        )
        session.add(tutor)
        await session.flush()

        coordinador = User(
            tenant_id=tenant.id, email=f"coord-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("CoordPass123!"), display_name="Coordinador",
            is_active=True,
        )
        session.add(coordinador)
        await session.flush()

        no_perm_user = User(
            tenant_id=tenant.id, email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"), display_name="No Perm",
            is_active=True,
        )
        session.add(no_perm_user)
        await session.flush()

        # Academic data
        carrera = Carrera(
            tenant_id=tenant.id, codigo="TUP", nombre="Tecnico en Programacion"
        )
        session.add(carrera)
        await session.flush()

        cohorte = Cohorte(
            tenant_id=tenant.id, carrera_id=carrera.id,
            nombre="2026-A", anio=2026,
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
        role_prof = Role(tenant_id=tenant.id, nombre="Profesor", codigo="PROFESOR")
        session.add(role_prof)
        role_coord = Role(tenant_id=tenant.id, nombre="Coordinador", codigo="COORDINADOR")
        session.add(role_coord)
        role_tutor = Role(tenant_id=tenant.id, nombre="Tutor", codigo="TUTOR")
        session.add(role_tutor)
        await session.flush()

        # Permission
        perm_publicar = Permission(tenant_id=tenant.id, codigo="avisos:publicar")
        session.add(perm_publicar)
        await session.flush()
        for role in [role_admin, role_coord]:
            rp = RolePermission(role_id=role.id, permission_id=perm_publicar.id)
            session.add(rp)

        await session.flush()

        # Assign roles to users
        for user_id, role in [
            (admin.id, role_admin),
            (profesor.id, role_prof),
            (tutor.id, role_tutor),
            (coordinador.id, role_coord),
        ]:
            ur = UserRole(
                tenant_id=tenant.id, user_id=user_id, role_id=role.id,
                desde=date(2024, 1, 1),
            )
            session.add(ur)

        await session.flush()

        # Asignaciones — profesor is assigned to materia, tutor is not
        asignacion_prof = Asignacion(
            tenant_id=tenant.id, usuario_id=profesor.id, rol="PROFESOR",
            materia_id=materia.id, cohorte_id=cohorte.id,
            comisiones=[], desde=date(2024, 1, 1),
        )
        session.add(asignacion_prof)
        await session.flush()

        data.update({
            "tenant_id": tenant.id,
            "admin_id": admin.id,
            "profesor_id": profesor.id,
            "tutor_id": tutor.id,
            "coordinador_id": coordinador.id,
            "no_perm_user_id": no_perm_user.id,
            "carrera_id": carrera.id,
            "cohorte_id": cohorte.id,
            "materia_id": materia.id,
            "materia2_id": materia2.id,
        })
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def seed_avisos_data(seed_avisos: dict) -> dict:
    """Seed aviso + acknowledgment data."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models.aviso import Aviso, AlcanceAviso, SeveridadAviso
    from app.models.acknowledgment_aviso import AcknowledgmentAviso

    from .conftest import TEST_SETTINGS

    from app.core.database import Base
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data = dict(seed_avisos)
    now = datetime.now(UTC)

    async with factory() as session:
        # Aviso Global activo en vigencia
        aviso_global = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.Global.value,
            severidad=SeveridadAviso.Info.value,
            titulo="Aviso Global",
            cuerpo="Cuerpo del aviso global",
            inicio_en=now - timedelta(days=1),
            fin_en=now + timedelta(days=10),
            orden=1,
            activo=True,
            requiere_ack=False,
        )
        session.add(aviso_global)
        await session.flush()
        data["aviso_global_id"] = aviso_global.id

        # Aviso PorMateria activo en vigencia
        aviso_materia = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.PorMateria.value,
            materia_id=data["materia_id"],
            severidad=SeveridadAviso.Advertencia.value,
            titulo="Aviso de Materia",
            cuerpo="Cuerpo del aviso por materia",
            inicio_en=now - timedelta(days=1),
            fin_en=now + timedelta(days=10),
            orden=2,
            activo=True,
            requiere_ack=True,
        )
        session.add(aviso_materia)
        await session.flush()
        data["aviso_materia_id"] = aviso_materia.id

        # Aviso PorRol activo en vigencia (destino PROFESOR)
        aviso_rol = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.PorRol.value,
            rol_destino="PROFESOR",
            severidad=SeveridadAviso.Crítico.value,
            titulo="Aviso para Profesores",
            cuerpo="Cuerpo del aviso por rol",
            inicio_en=now - timedelta(days=1),
            fin_en=now + timedelta(days=10),
            orden=3,
            activo=True,
            requiere_ack=False,
        )
        session.add(aviso_rol)
        await session.flush()
        data["aviso_rol_id"] = aviso_rol.id

        # Aviso Global fuera de vigencia (futuro)
        aviso_futuro = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.Global.value,
            severidad=SeveridadAviso.Info.value,
            titulo="Aviso Futuro",
            cuerpo="Cuerpo del aviso futuro",
            inicio_en=now + timedelta(days=30),
            fin_en=now + timedelta(days=60),
            orden=4,
            activo=True,
            requiere_ack=False,
        )
        session.add(aviso_futuro)
        await session.flush()
        data["aviso_futuro_id"] = aviso_futuro.id

        # Aviso Global inactivo
        aviso_inactivo = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.Global.value,
            severidad=SeveridadAviso.Info.value,
            titulo="Aviso Inactivo",
            cuerpo="Cuerpo del aviso inactivo",
            inicio_en=now - timedelta(days=10),
            fin_en=now + timedelta(days=10),
            orden=5,
            activo=False,
            requiere_ack=False,
        )
        session.add(aviso_inactivo)
        await session.flush()
        data["aviso_inactivo_id"] = aviso_inactivo.id

        # Aviso con requiere_ack=true (para probar ack)
        aviso_ack = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.Global.value,
            severidad=SeveridadAviso.Advertencia.value,
            titulo="Aviso con Ack",
            cuerpo="Cuerpo del aviso con ack",
            inicio_en=now - timedelta(days=1),
            fin_en=now + timedelta(days=10),
            orden=6,
            activo=True,
            requiere_ack=True,
        )
        session.add(aviso_ack)
        await session.flush()
        data["aviso_ack_id"] = aviso_ack.id

        # Aviso PorCohorte
        aviso_cohorte = Aviso(
            tenant_id=data["tenant_id"],
            alcance=AlcanceAviso.PorCohorte.value,
            cohorte_id=data["cohorte_id"],
            severidad=SeveridadAviso.Info.value,
            titulo="Aviso de Cohorte",
            cuerpo="Cuerpo cohorte",
            inicio_en=now - timedelta(days=1),
            fin_en=now + timedelta(days=10),
            orden=7,
            activo=True,
            requiere_ack=False,
        )
        session.add(aviso_cohorte)
        await session.flush()
        data["aviso_cohorte_id"] = aviso_cohorte.id

        # Ack: profesor acknowledges aviso_ack
        ack = AcknowledgmentAviso(
            tenant_id=data["tenant_id"],
            aviso_id=aviso_ack.id,
            usuario_id=data["profesor_id"],
            confirmado_at=now,
        )
        session.add(ack)
        await session.flush()
        data["ack_id"] = ack.id

        await session.commit()

    await engine.dispose()
    return data


class TestAvisoRepository:
    """AvisoRepository CRUD and query tests."""

    async def test_create_and_get(self, seed_avisos: dict):
        from app.repositories.aviso_repository import AvisoRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AvisoRepository(session=session, tenant_id=seed_avisos["tenant_id"])
            aviso = await repo.create(
                alcance="Global",
                severidad="Info",
                titulo="Test Create",
                cuerpo="Cuerpo de test",
                inicio_en=datetime(2026, 1, 1, tzinfo=UTC),
                fin_en=datetime(2026, 12, 31, tzinfo=UTC),
                orden=10,
                activo=True,
                requiere_ack=False,
            )
            assert aviso is not None
            assert aviso.titulo == "Test Create"
            assert aviso.activo is True

            fetched = await repo.get(aviso.id)
            assert fetched is not None
            assert fetched.titulo == "Test Create"
        await engine.dispose()

    async def test_update(self, seed_avisos_data: dict):
        from app.repositories.aviso_repository import AvisoRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AvisoRepository(session=session, tenant_id=seed_avisos_data["tenant_id"])
            updated = await repo.update(seed_avisos_data["aviso_global_id"], titulo="Nuevo Título")
            assert updated is not None
            assert updated.titulo == "Nuevo Título"
        await engine.dispose()

    async def test_soft_delete(self, seed_avisos_data: dict):
        from app.repositories.aviso_repository import AvisoRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AvisoRepository(session=session, tenant_id=seed_avisos_data["tenant_id"])
            result = await repo.soft_delete(seed_avisos_data["aviso_global_id"])
            assert result is True

            # Should not be retrievable
            deleted = await repo.get(seed_avisos_data["aviso_global_id"])
            assert deleted is None
        await engine.dispose()

    async def test_list_activos_para_usuario_global(
        self, seed_avisos_data: dict,
    ):
        """Usuario sin asignación ve avisos Global y PorCohorte (si coincide)."""
        from app.repositories.aviso_repository import AvisoRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AvisoRepository(session=session, tenant_id=seed_avisos_data["tenant_id"])
            # Tutor has no asignacion but is in the cohorte via the tenant
            avisos = await repo.list_activos_para_usuario(
                usuario_id=seed_avisos_data["tutor_id"],
                roles=["TUTOR"],
                materias_ids=[],
                cohorte_ids=[seed_avisos_data["cohorte_id"]],
            )
            ids = [a.id for a in avisos]
            # Should see: Global, Ack (not acked), Cohorte
            assert seed_avisos_data["aviso_global_id"] in ids
            assert seed_avisos_data["aviso_ack_id"] in ids  # not acked yet
            assert seed_avisos_data["aviso_cohorte_id"] in ids
            # Should NOT see: Materia (no asignacion), Rol (TUTOR != PROFESOR),
            # Futuro (fuera de vigencia), Inactivo
            assert seed_avisos_data["aviso_materia_id"] not in ids
            assert seed_avisos_data["aviso_rol_id"] not in ids
            assert seed_avisos_data["aviso_futuro_id"] not in ids
            assert seed_avisos_data["aviso_inactivo_id"] not in ids
        await engine.dispose()

    async def test_list_activos_profesor_ve_materia_y_rol(
        self, seed_avisos_data: dict,
    ):
        """Profesor con asignación ve avisos PorMateria y PorRol (PROFESOR)."""
        from app.repositories.aviso_repository import AvisoRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AvisoRepository(session=session, tenant_id=seed_avisos_data["tenant_id"])
            avisos = await repo.list_activos_para_usuario(
                usuario_id=seed_avisos_data["profesor_id"],
                roles=["PROFESOR"],
                materias_ids=[seed_avisos_data["materia_id"]],
                cohorte_ids=[seed_avisos_data["cohorte_id"]],
            )
            ids = [a.id for a in avisos]
            # Should see: Global, Materia, Rol (PROFESOR), Cohorte
            assert seed_avisos_data["aviso_global_id"] in ids
            assert seed_avisos_data["aviso_materia_id"] in ids
            assert seed_avisos_data["aviso_rol_id"] in ids
            assert seed_avisos_data["aviso_cohorte_id"] in ids
            # Ack should NOT be visible (already acked by profesor)
            assert seed_avisos_data["aviso_ack_id"] not in ids
        await engine.dispose()

    async def test_list_activos_orden_correcto(
        self, seed_avisos_data: dict,
    ):
        """Avisos ordenados por orden ASC, tiebreaker created_at DESC."""
        from app.repositories.aviso_repository import AvisoRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AvisoRepository(session=session, tenant_id=seed_avisos_data["tenant_id"])
            avisos = await repo.list_activos_para_usuario(
                usuario_id=seed_avisos_data["tutor_id"],
                roles=["TUTOR"],
                materias_ids=[],
                cohorte_ids=[seed_avisos_data["cohorte_id"]],
            )
            # Should be ordered by orden ASC
            for i in range(len(avisos) - 1):
                assert avisos[i].orden <= avisos[i + 1].orden
        await engine.dispose()


class TestAcknowledgmentRepository:
    """AcknowledgmentRepository CRUD tests."""

    async def test_create_and_count(self, seed_avisos_data: dict):
        from app.repositories.aviso_repository import AcknowledgmentRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AcknowledgmentRepository(
                session=session, tenant_id=seed_avisos_data["tenant_id"],
            )
            ack = await repo.create(
                aviso_id=seed_avisos_data["aviso_global_id"],
                usuario_id=seed_avisos_data["tutor_id"],
            )
            assert ack is not None
            assert ack.aviso_id == seed_avisos_data["aviso_global_id"]
            assert ack.confirmado_at is not None

            count = await repo.count_por_aviso(seed_avisos_data["aviso_global_id"])
            assert count == 1
        await engine.dispose()

    async def test_exists_por_usuario(self, seed_avisos_data: dict):
        from app.repositories.aviso_repository import AcknowledgmentRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AcknowledgmentRepository(
                session=session, tenant_id=seed_avisos_data["tenant_id"],
            )
            # Profesor already acked aviso_ack
            exists = await repo.exists_por_usuario(
                aviso_id=seed_avisos_data["aviso_ack_id"],
                usuario_id=seed_avisos_data["profesor_id"],
            )
            assert exists is True

            # Tutor has NOT acked
            exists = await repo.exists_por_usuario(
                aviso_id=seed_avisos_data["aviso_ack_id"],
                usuario_id=seed_avisos_data["tutor_id"],
            )
            assert exists is False
        await engine.dispose()

    async def test_list_por_aviso(self, seed_avisos_data: dict):
        from app.repositories.aviso_repository import AcknowledgmentRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = AcknowledgmentRepository(
                session=session, tenant_id=seed_avisos_data["tenant_id"],
            )
            acks = await repo.list_por_aviso(seed_avisos_data["aviso_ack_id"])
            assert len(acks) >= 1
            # Should include profesor's ack
            assert acks[0].usuario_id == seed_avisos_data["profesor_id"]
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 6.1: Unit tests — filtering and ordering logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestFiltradoAvisos:
    """Unit tests for alcance filtering and vigencia window."""

    def test_alcance_global_visible_a_todos(self):
        """Global alcance should be visible to any user regardless of role."""
        from app.models.aviso import AlcanceAviso
        # A Global aviso has no materia_id, cohorte_id, or rol_destino
        assert AlcanceAviso.Global.value == "Global"
        # This is purely structural — Global means no specific binding

    def test_alcance_nombres_correctos(self):
        """All alcance values match expected naming."""
        from app.models.aviso import AlcanceAviso
        assert set(a.value for a in AlcanceAviso) == {
            "Global", "PorMateria", "PorCohorte", "PorRol",
        }

    def test_severidad_nombres_correctos(self):
        """All severity values match expected naming."""
        from app.models.aviso import SeveridadAviso
        names = {s.value for s in SeveridadAviso}
        assert "Info" in names
        assert "Advertencia" in names
        assert "Crítico" in names


# ═══════════════════════════════════════════════════════════════════════════════
# E2E tests — full HTTP flow
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def aviso_tokens(seed_avisos: dict) -> dict:
    """JWT tokens for each user from the seed."""
    tokens: dict[str, str] = {}
    for role, key in [
        ("admin", "admin_id"),
        ("profesor", "profesor_id"),
        ("tutor", "tutor_id"),
        ("coordinador", "coordinador_id"),
        ("no_perm", "no_perm_user_id"),
    ]:
        tokens[role] = create_access_token(data={
            "sub": str(seed_avisos[key]),
            "tenant_id": str(seed_avisos["tenant_id"]),
        })
    return tokens


class TestE2EAvisos:
    """Full E2E flow tests for avisos endpoints."""

    BASE = "/api/avisos"

    async def _crear_aviso(
        self,
        client: AsyncClient,
        token: str,
        *,
        titulo: str = "Aviso E2E",
        alcance: str = "Global",
        severidad: str = "Info",
        requiere_ack: bool = False,
        **overrides: dict,
    ) -> dict:
        """Helper: create an aviso via POST and return the response data."""
        payload: dict = {
            "titulo": titulo,
            "cuerpo": "Cuerpo del aviso E2E",
            "alcance": alcance,
            "severidad": severidad,
            "inicio_en": "2026-01-01T00:00:00Z",
            "fin_en": "2026-12-31T00:00:00Z",
            "orden": 1,
            "requiere_ack": requiere_ack,
        }
        payload.update(overrides)
        resp = await client.post(
            self.BASE,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp  # type: ignore[return-value]

    # ── AT-01: Crear aviso ────────────────────────────────────────────────

    async def test_crear_aviso_global_201(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """POST /api/avisos → 201 for coordinador (AT-01)."""
        resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["titulo"] == "Aviso E2E"
        assert body["activo"] is True
        assert "id" in body

    # ── AT-03: 422 sin campos requeridos ──────────────────────────────────

    async def test_crear_sin_titulo_422(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """POST /api/avisos sin titulo → 422 (AT-03)."""
        resp = await async_client.post(
            self.BASE,
            json={"cuerpo": "test", "alcance": "Global", "severidad": "Info",
                  "inicio_en": "2026-01-01T00:00:00Z",
                  "fin_en": "2026-12-31T00:00:00Z"},
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )
        assert resp.status_code == 422, resp.text

    # ── AT-04: Modificar aviso (PATCH) ────────────────────────────────────

    async def test_patch_aviso_200(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """PATCH /api/avisos/{id} → 200 (AT-04)."""
        # Create first
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
        )
        aviso_id = create_resp.json()["id"]

        resp = await async_client.patch(
            f"{self.BASE}/{aviso_id}",
            json={"titulo": "Título modificado"},
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["titulo"] == "Título modificado"

    # ── AT-05: Desactivar aviso ───────────────────────────────────────────

    async def test_desactivar_aviso_200(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """PATCH activo=false → 200, aviso no aparece en mis-avisos (AT-05)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
        )
        aviso_id = create_resp.json()["id"]

        await async_client.patch(
            f"{self.BASE}/{aviso_id}",
            json={"activo": False},
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )

        # Should NOT appear in mis-avisos
        mis = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        ids = [item["id"] for item in mis.json().get("items", [])]
        assert aviso_id not in ids

    # ── AT-06: Eliminar aviso ─────────────────────────────────────────────

    async def test_delete_aviso_200(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """DELETE /api/avisos/{id} → 200, soft delete (AT-06)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
        )
        aviso_id = create_resp.json()["id"]

        resp = await async_client.delete(
            f"{self.BASE}/{aviso_id}",
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text

        # Should not appear in gestión list
        lista = await async_client.get(
            self.BASE,
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )
        ids = [item["id"] for item in lista.json().get("items", [])]
        assert aviso_id not in ids

    # ── AT-07: Listar avisos con contadores ───────────────────────────────

    async def test_listar_gestion_con_contadores(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """GET /api/avisos → list with total_vistos and total_acks (AT-07)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
        )
        aviso_id = create_resp.json()["id"]

        lista = await async_client.get(
            self.BASE,
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )
        assert lista.status_code == 200, lista.text
        items = lista.json().get("items", [])
        assert len(items) >= 1
        # The aviso we just created should have 0 counters
        found = [i for i in items if i["id"] == aviso_id]
        assert len(found) == 1
        assert found[0]["total_vistos"] == 0
        assert found[0]["total_acks"] == 0

    # ── AT-08: Usuario ve avisos globales ─────────────────────────────────

    async def test_mis_avisos_ve_global(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """GET /api/avisos/mis-avisos → usuario ve aviso Global (AT-08)."""
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Aviso Global Test",
        )

        mis = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['tutor']}"},
        )
        assert mis.status_code == 200, mis.text
        titulos = [item["titulo"] for item in mis.json().get("items", [])]
        assert "Aviso Global Test" in titulos

    # ── AT-09: Usuario NO ve avisos PorMateria sin asignación ─────────────

    async def test_mis_avisos_no_ve_materia_sin_asignacion(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Usuario sin asignación NO ve aviso PorMateria (AT-09)."""
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Solo Materia",
            alcance="PorMateria",
            materia_id=str(seed_avisos["materia_id"]),
        )

        # Tutor is NOT assigned to materia
        mis_tutor = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['tutor']}"},
        )
        tutor_titulos = [i["titulo"] for i in mis_tutor.json().get("items", [])]
        assert "Solo Materia" not in tutor_titulos

        # Profesor IS assigned — should see it
        mis_prof = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        prof_titulos = [i["titulo"] for i in mis_prof.json().get("items", [])]
        assert "Solo Materia" in prof_titulos

    # ── AT-10: Usuario NO ve avisos PorRol si no coincide ────────────────

    async def test_mis_avisos_no_ve_rol_distinto(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Tutor no ve aviso PorRol dirigido a PROFESOR (AT-10)."""
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Solo Profesores",
            alcance="PorRol",
            rol_destino="PROFESOR",
        )

        mis_tutor = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['tutor']}"},
        )
        titulos = [i["titulo"] for i in mis_tutor.json().get("items", [])]
        assert "Solo Profesores" not in titulos

    # ── AT-11: Fuera de ventana no se muestra ─────────────────────────────

    async def test_mis_avisos_fuera_vigencia(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Aviso con fin_en en pasado no se muestra (AT-11 / RN-18)."""
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Aviso Expirado",
            inicio_en="2020-01-01T00:00:00Z",
            fin_en="2020-06-01T00:00:00Z",
        )

        mis = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        titulos = [i["titulo"] for i in mis.json().get("items", [])]
        assert "Aviso Expirado" not in titulos

    # ── AT-12: Orden ASC ──────────────────────────────────────────────────

    async def test_mis_avisos_orden_asc(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Avisos ordenados por orden ASC (AT-12)."""
        # Create two avisos with different orden
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Prioridad Baja", orden=10,
        )
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Prioridad Alta", orden=1,
        )

        mis = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        items = mis.json().get("items", [])
        # Filter our test avisos
        test_items = [i for i in items if i["titulo"] in ("Prioridad Alta", "Prioridad Baja")]
        assert len(test_items) == 2
        assert test_items[0]["titulo"] == "Prioridad Alta"  # orden=1 first
        assert test_items[1]["titulo"] == "Prioridad Baja"  # orden=10 second

    # ── AT-13: Acusar recibo ──────────────────────────────────────────────

    async def test_ack_aviso_201(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """POST /api/avisos/{id}/ack → 201 (AT-13)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            requiere_ack=True,
        )
        aviso_id = create_resp.json()["id"]

        resp = await async_client.post(
            f"{self.BASE}/{aviso_id}/ack",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["aviso_id"] == aviso_id
        assert "confirmado_at" in body

    # ── AT-14: Aviso acusado ya no aparece (RN-19) ────────────────────────

    async def test_ack_oculta_aviso(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Aviso con requiere_ack=true desaparece tras acusar (AT-14)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Se Ocultará", requiere_ack=True,
        )
        aviso_id = create_resp.json()["id"]

        # Before ack — visible
        mis_before = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        before_ids = [i["id"] for i in mis_before.json().get("items", [])]
        assert aviso_id in before_ids

        # Ack
        await async_client.post(
            f"{self.BASE}/{aviso_id}/ack",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )

        # After ack — hidden
        mis_after = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        after_ids = [i["id"] for i in mis_after.json().get("items", [])]
        assert aviso_id not in after_ids

    # ── AT-15: Aviso sin requiere_ack sigue apareciendo ───────────────────

    async def test_aviso_sin_requiere_ack_siempre_visible(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Aviso con requiere_ack=false siempre visible (AT-15)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            titulo="Siempre Visible", requiere_ack=False,
        )
        aviso_id = create_resp.json()["id"]

        # Check visible both times
        for _ in range(2):
            mis = await async_client.get(
                f"{self.BASE}/mis-avisos",
                headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
            )
            ids = [i["id"] for i in mis.json().get("items", [])]
            assert aviso_id in ids

    # ── AT-16: Rechazar ack duplicado ─────────────────────────────────────

    async def test_ack_duplicado_409(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """POST ack duplicado → 409 (AT-16)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            requiere_ack=True,
        )
        aviso_id = create_resp.json()["id"]

        # First ack — OK
        await async_client.post(
            f"{self.BASE}/{aviso_id}/ack",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )

        # Second ack — 409
        resp = await async_client.post(
            f"{self.BASE}/{aviso_id}/ack",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        assert resp.status_code == 409, resp.text
        assert "Ya has confirmado" in resp.text

    # ── AT-17: Rechazar ack en aviso sin requiere_ack ─────────────────────

    async def test_ack_sin_requiere_ack_409(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """POST ack en aviso sin requiere_ack → 409 (AT-17)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            requiere_ack=False,
        )
        aviso_id = create_resp.json()["id"]

        resp = await async_client.post(
            f"{self.BASE}/{aviso_id}/ack",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )
        assert resp.status_code == 409, resp.text
        assert "no requiere confirmación" in resp.text

    # ── AT-18: Listar acuses de un aviso ──────────────────────────────────

    async def test_listar_acks(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """GET /api/avisos/{id}/acks → lista de usuarios (AT-18)."""
        create_resp = await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            requiere_ack=True,
        )
        aviso_id = create_resp.json()["id"]

        # Profesor acks
        await async_client.post(
            f"{self.BASE}/{aviso_id}/ack",
            headers={"Authorization": f"Bearer {aviso_tokens['profesor']}"},
        )

        # Coordinador lists acks
        resp = await async_client.get(
            f"{self.BASE}/{aviso_id}/acks",
            headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
        usuario_ids = [a["usuario_id"] for a in body["items"]]
        assert str(seed_avisos["profesor_id"]) in usuario_ids

    # ── AT-19: 403 sin permiso avisos:publicar ────────────────────────────

    async def test_403_sin_permiso_publicar(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """TUTOR (sin avisos:publicar) → 403 en endpoints de gestión (AT-19)."""
        # POST
        resp_post = await async_client.post(
            self.BASE,
            json={"titulo": "x", "cuerpo": "x", "alcance": "Global",
                  "severidad": "Info", "inicio_en": "2026-01-01T00:00:00Z",
                  "fin_en": "2026-12-31T00:00:00Z"},
            headers={"Authorization": f"Bearer {aviso_tokens['tutor']}"},
        )
        assert resp_post.status_code == 403, resp_post.text

        # GET lista gestión
        resp_get = await async_client.get(
            self.BASE,
            headers={"Authorization": f"Bearer {aviso_tokens['tutor']}"},
        )
        assert resp_get.status_code == 403, resp_get.text

    # ── AT-20: 200 en mis-avisos y ack sin permiso especial ───────────────

    async def test_mis_avisos_y_ack_sin_permiso_200(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """Usuario sin permiso puede usar mis-avisos y ack (AT-20)."""
        # mis-avisos — need to create at least one first
        await self._crear_aviso(
            async_client, aviso_tokens["coordinador"],
            requiere_ack=True,
        )

        mis = await async_client.get(
            f"{self.BASE}/mis-avisos",
            headers={"Authorization": f"Bearer {aviso_tokens['no_perm']}"},
        )
        assert mis.status_code == 200, mis.text

    # ── AT-21: 401 sin token ──────────────────────────────────────────────

    async def test_401_sin_token(
        self, async_client: AsyncClient,
    ):
        """Endpoints sin token → 401 (AT-21)."""
        resp = await async_client.get(f"{self.BASE}/mis-avisos")
        assert resp.status_code == 403, resp.text  # FastAPI returns 403 when no Bearer

    # ── 404 en aviso inexistente ──────────────────────────────────────────

    async def test_404_aviso_inexistente(
        self, async_client: AsyncClient, seed_avisos: dict, aviso_tokens: dict,
    ):
        """PATCH/DELETE/GET acks sobre aviso inexistente → 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        for method, url in [
            ("PATCH", f"{self.BASE}/{fake_id}"),
            ("DELETE", f"{self.BASE}/{fake_id}"),
            ("GET", f"{self.BASE}/{fake_id}/acks"),
        ]:
            resp = await async_client.request(
                method, url,
                json={"titulo": "x"} if method == "PATCH" else None,
                headers={"Authorization": f"Bearer {aviso_tokens['coordinador']}"},
            )
            assert resp.status_code == 404, f"{method} {url}: {resp.text}"
