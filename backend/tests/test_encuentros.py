"""Tests for Encuentros and Guardias modules (C-13).

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
async def seed_data(async_client: AsyncClient) -> dict:
    """Minimal seed: tenant + users + roles + academic data + asignaciones."""
    from app.core.security import hash_password

    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Encuentros Tenant", codigo=f"EN{uuid.uuid4().hex[:4]}")
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

        # Permissions
        perm_encuentros = Permission(tenant_id=tenant.id, codigo="encuentros:gestionar")
        session.add(perm_encuentros)
        await session.flush()
        for role in [role_admin, role_prof, role_coord]:
            session.add(RolePermission(role_id=role.id, permission_id=perm_encuentros.id))

        perm_guardias = Permission(tenant_id=tenant.id, codigo="guardias:gestionar")
        session.add(perm_guardias)
        await session.flush()
        for role in [role_admin, role_prof, role_coord]:
            session.add(RolePermission(role_id=role.id, permission_id=perm_guardias.id))

        await session.flush()

        # Assign roles to users
        for user_id, role in [
            (admin.id, role_admin),
            (profesor.id, role_prof),
            (coordinador.id, role_coord),
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

        asignacion_other = Asignacion(
            tenant_id=tenant.id,
            usuario_id=admin.id,
            rol="COORDINADOR",
            materia_id=materia2.id,
            cohorte_id=cohorte.id,
            comisiones=[],
            desde=date(2024, 1, 1),
        )
        session.add(asignacion_other)
        await session.flush()

        data.update({
            "tenant_id": tenant.id,
            "admin_id": admin.id,
            "profesor_id": profesor.id,
            "coordinador_id": coordinador.id,
            "no_perm_user_id": no_perm_user.id,
            "carrera_id": carrera.id,
            "cohorte_id": cohorte.id,
            "materia_id": materia.id,
            "materia2_id": materia2.id,
            "asignacion_prof_id": asignacion_prof.id,
            "asignacion_other_id": asignacion_other.id,
        })
        await session.commit()

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1 tests: Model definitions
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlotEncuentroModel:
    """SlotEncuentro model — structural tests."""

    def test_imports(self):
        """SlotEncuentro model can be imported."""
        from app.models.slot_encuentro import SlotEncuentro
        assert SlotEncuentro.__tablename__ == "slot_encuentro"

    def test_fields_exist(self):
        """SlotEncuentro has expected columns."""
        from app.models.slot_encuentro import SlotEncuentro
        cols = {c.name for c in SlotEncuentro.__table__.columns}
        assert "titulo" in cols
        assert "hora" in cols
        assert "dia_semana" in cols
        assert "fecha_inicio" in cols
        assert "cant_semanas" in cols
        assert "fecha_unica" in cols
        assert "meet_url" in cols
        assert "vig_desde" in cols
        assert "vig_hasta" in cols
        assert "tenant_id" in cols
        assert "asignacion_id" in cols
        assert "materia_id" in cols


class TestEstadoInstancia:
    """EstadoInstancia enum."""

    def test_enum_values(self):
        from app.models.instancia_encuentro import EstadoInstancia
        assert EstadoInstancia.Programado.value == "Programado"
        assert EstadoInstancia.Realizado.value == "Realizado"
        assert EstadoInstancia.Cancelado.value == "Cancelado"


class TestInstanciaEncuentroModel:
    """InstanciaEncuentro model — structural tests."""

    def test_imports(self):
        from app.models.instancia_encuentro import InstanciaEncuentro
        assert InstanciaEncuentro.__tablename__ == "instancia_encuentro"

    def test_fields_exist(self):
        from app.models.instancia_encuentro import InstanciaEncuentro
        cols = {c.name for c in InstanciaEncuentro.__table__.columns}
        assert "slot_id" in cols
        assert "materia_id" in cols
        assert "fecha" in cols
        assert "hora" in cols
        assert "titulo" in cols
        assert "estado" in cols
        assert "meet_url" in cols
        assert "video_url" in cols
        assert "comentario" in cols
        assert "tenant_id" in cols


class TestEstadoGuardia:
    """EstadoGuardia enum."""

    def test_enum_values(self):
        from app.models.guardia import EstadoGuardia
        assert EstadoGuardia.Pendiente.value == "Pendiente"
        assert EstadoGuardia.Realizada.value == "Realizada"
        assert EstadoGuardia.Cancelada.value == "Cancelada"


class TestGuardiaModel:
    """Guardia model — structural tests."""

    def test_imports(self):
        from app.models.guardia import Guardia
        assert Guardia.__tablename__ == "guardia"

    def test_fields_exist(self):
        from app.models.guardia import Guardia
        cols = {c.name for c in Guardia.__table__.columns}
        assert "asignacion_id" in cols
        assert "materia_id" in cols
        assert "carrera_id" in cols
        assert "cohorte_id" in cols
        assert "dia" in cols
        assert "horario" in cols
        assert "estado" in cols
        assert "comentarios" in cols
        assert "creada_at" in cols
        assert "tenant_id" in cols


class TestEncuentrosModelInit:
    """Models can be instantiated in __init__."""

    def test_slot_encuentro_exported(self):
        from app.models import SlotEncuentro
        assert SlotEncuentro.__tablename__ == "slot_encuentro"

    def test_instancia_encuentro_exported(self):
        from app.models import InstanciaEncuentro
        assert InstanciaEncuentro.__tablename__ == "instancia_encuentro"

    def test_estado_instancia_exported(self):
        from app.models import EstadoInstancia
        assert EstadoInstancia.Programado.value == "Programado"

    def test_guardia_exported(self):
        from app.models import Guardia
        assert Guardia.__tablename__ == "guardia"

    def test_estado_guardia_exported(self):
        from app.models import EstadoGuardia
        assert EstadoGuardia.Pendiente.value == "Pendiente"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2 tests: Repositories
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_encuentros(seed_data: dict) -> dict:
    """Seed slot_encuentro + instancia_encuentro + guardia data."""
    import uuid as _uuid

    from app.models.slot_encuentro import SlotEncuentro
    from app.models.instancia_encuentro import InstanciaEncuentro, EstadoInstancia
    from app.models.guardia import Guardia, EstadoGuardia

    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data = dict(seed_data)

    async with factory() as session:
        # Slot recurrente
        slot = SlotEncuentro(
            tenant_id=data["tenant_id"],
            asignacion_id=data["asignacion_prof_id"],
            materia_id=data["materia_id"],
            titulo="Clase de PROG1",
            hora="18:00",
            dia_semana="Lunes",
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=15,
            meet_url="https://meet.google.com/test",
            vig_desde=date(2026, 3, 1),
        )
        session.add(slot)
        await session.flush()
        data["slot_id"] = slot.id

        # Slot fecha única
        slot_unico = SlotEncuentro(
            tenant_id=data["tenant_id"],
            asignacion_id=data["asignacion_prof_id"],
            materia_id=data["materia_id"],
            titulo="Clase Inaugural",
            hora="18:00",
            dia_semana="Lunes",
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=0,
            fecha_unica=date(2026, 3, 10),
            meet_url="https://meet.google.com/unique",
            vig_desde=date(2026, 3, 1),
            vig_hasta=date(2026, 12, 31),
        )
        session.add(slot_unico)
        await session.flush()
        data["slot_unico_id"] = slot_unico.id

        # Instancias del slot recurrente
        instancias = []
        for i in range(15):
            inst = InstanciaEncuentro(
                tenant_id=data["tenant_id"],
                slot_id=slot.id,
                materia_id=data["materia_id"],
                fecha=date(2026, 3, 10) + timedelta(weeks=i),
                hora="18:00",
                titulo=f"Clase #{i+1}",
                estado=EstadoInstancia.Programado.value,
                meet_url="https://meet.google.com/test",
            )
            instancias.append(inst)
        session.add_all(instancias)
        await session.flush()
        data["instancia_ids"] = [i.id for i in instancias]

        # Instancia para otra materia (scope test)
        inst_otra = InstanciaEncuentro(
            tenant_id=data["tenant_id"],
            materia_id=data["materia2_id"],
            fecha=date(2026, 4, 1),
            hora="19:00",
            titulo="Clase de PROG2",
            estado=EstadoInstancia.Programado.value,
        )
        session.add(inst_otra)
        await session.flush()
        data["instancia_otra_id"] = inst_otra.id

        # Guardias
        guardia = Guardia(
            tenant_id=data["tenant_id"],
            asignacion_id=data["asignacion_prof_id"],
            materia_id=data["materia_id"],
            carrera_id=data["carrera_id"],
            cohorte_id=data["cohorte_id"],
            dia="Lunes",
            horario="14:00-14:45",
            estado=EstadoGuardia.Pendiente.value,
            comentarios="Consulta TP2",
        )
        session.add(guardia)
        await session.flush()
        data["guardia_id"] = guardia.id

        guardia_realizada = Guardia(
            tenant_id=data["tenant_id"],
            asignacion_id=data["asignacion_prof_id"],
            materia_id=data["materia_id"],
            carrera_id=data["carrera_id"],
            cohorte_id=data["cohorte_id"],
            dia="Martes",
            horario="15:00-15:45",
            estado=EstadoGuardia.Realizada.value,
            comentarios="Se resolvieron dudas",
            creada_at=datetime.now(UTC),
        )
        session.add(guardia_realizada)
        await session.flush()
        data["guardia_realizada_id"] = guardia_realizada.id

        await session.commit()

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Repository tests (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlotEncuentroRepository:
    """SlotEncuentroRepository CRUD tests."""

    async def test_create_and_get(self, seed_encuentros: dict):
        from app.repositories.encuentro_repository import SlotEncuentroRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = SlotEncuentroRepository(session=session, tenant_id=seed_encuentros["tenant_id"])
            slot = await repo.get(seed_encuentros["slot_id"])
            assert slot is not None
            assert slot.titulo == "Clase de PROG1"
            assert slot.cant_semanas == 15
            assert slot.fecha_unica is None
        await engine.dispose()

    async def test_list_por_materia(self, seed_encuentros: dict):
        from app.repositories.encuentro_repository import SlotEncuentroRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = SlotEncuentroRepository(session=session, tenant_id=seed_encuentros["tenant_id"])
            slots = await repo.list_por_materia(seed_encuentros["materia_id"])
            assert len(slots) >= 2  # recurrente + unico
        await engine.dispose()

    async def test_soft_delete(self, seed_encuentros: dict):
        from app.repositories.encuentro_repository import SlotEncuentroRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = SlotEncuentroRepository(session=session, tenant_id=seed_encuentros["tenant_id"])
            deleted = await repo.soft_delete(seed_encuentros["slot_id"])
            assert deleted is True
            slot = await repo.get(seed_encuentros["slot_id"])
            assert slot is None  # soft deleted
        await engine.dispose()


class TestInstanciaEncuentroRepository:
    """InstanciaEncuentroRepository CRUD tests."""

    async def test_list_por_materia_fechas(self, seed_encuentros: dict):
        from app.repositories.encuentro_repository import InstanciaEncuentroRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = InstanciaEncuentroRepository(
                session=session, tenant_id=seed_encuentros["tenant_id"]
            )
            instancias = await repo.list_por_materia_fechas(
                materia_id=seed_encuentros["materia_id"],
                desde=date(2026, 3, 1),
                hasta=date(2026, 7, 1),
            )
            assert len(instancias) == 15  # 15 instancias del slot recurrente
        await engine.dispose()

    async def test_update_estado(self, seed_encuentros: dict):
        from app.repositories.encuentro_repository import InstanciaEncuentroRepository
        from app.models.instancia_encuentro import EstadoInstancia

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = InstanciaEncuentroRepository(
                session=session, tenant_id=seed_encuentros["tenant_id"]
            )
            inst_id = seed_encuentros["instancia_ids"][0]
            updated = await repo.update_estado(
                id=inst_id,
                estado=EstadoInstancia.Realizado.value,
                video_url="https://youtube.com/watch?v=test",
            )
            assert updated is not None
            assert updated.estado == "Realizado"
            assert updated.video_url == "https://youtube.com/watch?v=test"
        await engine.dispose()

    async def test_count_por_materia(self, seed_encuentros: dict):
        from app.repositories.encuentro_repository import InstanciaEncuentroRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = InstanciaEncuentroRepository(
                session=session, tenant_id=seed_encuentros["tenant_id"]
            )
            count = await repo.count_por_materia(seed_encuentros["materia_id"])
            assert count == 15
        await engine.dispose()


class TestGuardiaRepository:
    """GuardiaRepository CRUD tests."""

    async def test_get(self, seed_encuentros: dict):
        from app.repositories.guardia_repository import GuardiaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = GuardiaRepository(session=session, tenant_id=seed_encuentros["tenant_id"])
            guardia = await repo.get(seed_encuentros["guardia_id"])
            assert guardia is not None
            assert guardia.dia == "Lunes"
            assert guardia.estado == "Pendiente"
        await engine.dispose()

    async def test_list_con_filtros(self, seed_encuentros: dict):
        from app.repositories.guardia_repository import GuardiaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = GuardiaRepository(session=session, tenant_id=seed_encuentros["tenant_id"])
            guardias = await repo.list_con_filtros(
                materia_id=seed_encuentros["materia_id"],
                estado="Pendiente",
            )
            assert len(guardias) == 1
            assert guardias[0].comentarios == "Consulta TP2"
        await engine.dispose()

    async def test_export_query(self, seed_encuentros: dict):
        from app.repositories.guardia_repository import GuardiaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            repo = GuardiaRepository(session=session, tenant_id=seed_encuentros["tenant_id"])
            guardias = await repo.export_query(
                materia_id=seed_encuentros["materia_id"],
            )
            assert len(guardias) == 2  # pendiente + realizada
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3 tests: Schemas
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlotCrearRequestSchema:
    """SlotCrearRequest schema validation."""

    def test_recurrente_valido(self):
        from app.schemas.encuentros import SlotCrearRequest

        data = SlotCrearRequest(
            materia_id=uuid.uuid4(),
            titulo="Clase de PROG1",
            hora="18:00",
            dia_semana="Lunes",
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=15,
            meet_url="https://meet.google.com/test",
        )
        assert data.cant_semanas == 15
        assert data.fecha_unica is None

    def test_fecha_unica_valido(self):
        from app.schemas.encuentros import SlotCrearRequest

        data = SlotCrearRequest(
            materia_id=uuid.uuid4(),
            titulo="Clase Inaugural",
            hora="18:00",
            dia_semana="Lunes",
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=0,
            fecha_unica=date(2026, 3, 10),
            meet_url="https://meet.google.com/test",
        )
        assert data.cant_semanas == 0
        assert data.fecha_unica == date(2026, 3, 10)

    def test_ambos_nulos_invalido(self):
        from pydantic import ValidationError
        from app.schemas.encuentros import SlotCrearRequest

        with pytest.raises(ValidationError):
            SlotCrearRequest(
                materia_id=uuid.uuid4(),
                titulo="Invalido",
                hora="18:00",
                dia_semana="Lunes",
                fecha_inicio=date(2026, 3, 10),
                cant_semanas=0,  # 0 pero fecha_unica=None → inválido
            )

    def test_ambos_seteados_invalido(self):
        from pydantic import ValidationError
        from app.schemas.encuentros import SlotCrearRequest

        with pytest.raises(ValidationError):
            SlotCrearRequest(
                materia_id=uuid.uuid4(),
                titulo="Invalido",
                hora="18:00",
                dia_semana="Lunes",
                fecha_inicio=date(2026, 3, 10),
                cant_semanas=5,
                fecha_unica=date(2026, 3, 10),  # Both set → inválido
            )

    def test_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.encuentros import SlotCrearRequest

        with pytest.raises(ValidationError):
            SlotCrearRequest(
                materia_id=uuid.uuid4(),
                titulo="Test",
                hora="18:00",
                dia_semana="Lunes",
                fecha_inicio=date(2026, 3, 10),
                cant_semanas=15,
                extra_field="should_fail",
            )


class TestInstanciaUpdateRequest:
    """InstanciaUpdateRequest schema."""

    def test_todos_opcionales(self):
        from app.schemas.encuentros import InstanciaUpdateRequest

        data = InstanciaUpdateRequest()
        assert data.estado is None
        assert data.video_url is None
        assert data.comentario is None

    def test_actualiza_campos(self):
        from app.schemas.encuentros import InstanciaUpdateRequest

        data = InstanciaUpdateRequest(
            estado="Realizado",
            video_url="https://youtube.com/test",
            comentario="Buena clase",
        )
        assert data.estado == "Realizado"
        assert data.video_url == "https://youtube.com/test"
        assert data.comentario == "Buena clase"

    def test_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.encuentros import InstanciaUpdateRequest

        with pytest.raises(ValidationError):
            InstanciaUpdateRequest(extra="bad")


class TestGuardiaSchemas:
    """Guardia schemas."""

    def test_crear_request_extra_forbid(self):
        from pydantic import ValidationError
        from app.schemas.guardias import GuardiaCrearRequest

        with pytest.raises(ValidationError):
            GuardiaCrearRequest(
                asignacion_id=uuid.uuid4(),
                materia_id=uuid.uuid4(),
                carrera_id=uuid.uuid4(),
                cohorte_id=uuid.uuid4(),
                dia="Lunes",
                horario="14:00-14:45",
                extra="bad",
            )

    def test_update_request(self):
        from app.schemas.guardias import GuardiaUpdateRequest

        data = GuardiaUpdateRequest(estado="Realizada", comentarios="Hecho")
        assert data.estado == "Realizada"

    def test_response_from_attributes(self):
        from app.schemas.guardias import GuardiaResponse

        data = GuardiaResponse(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            asignacion_id=uuid.uuid4(),
            materia_id=uuid.uuid4(),
            carrera_id=uuid.uuid4(),
            cohorte_id=uuid.uuid4(),
            dia="Lunes",
            horario="14:00-14:45",
            estado="Pendiente",
            comentarios=None,
            creada_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert data.dia == "Lunes"


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 tests: Service (pure functions)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGeneracionInstancias:
    """Instance generation logic — pure function tests."""

    def _call(self, *args, **kwargs):
        from app.services.encuentro_service import _generar_fechas_instancias
        return _generar_fechas_instancias(*args, **kwargs)

    def test_recurrente_15_semanas(self):
        """cant_semanas=15 → 15 fechas."""
        fechas = self._call(
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=15,
            fecha_unica=None,
            titulo="Clase",
            hora="18:00",
        )
        assert len(fechas) == 15
        assert fechas[0]["fecha"] == date(2026, 3, 10)
        assert fechas[1]["fecha"] == date(2026, 3, 17)
        assert fechas[14]["fecha"] == date(2026, 6, 16)  # 10 + 14*7

    def test_fecha_unica(self):
        """fecha_unica set → 1 fecha."""
        fechas = self._call(
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=0,
            fecha_unica=date(2026, 3, 10),
            titulo="Inaugural",
            hora="18:00",
        )
        assert len(fechas) == 1
        assert fechas[0]["fecha"] == date(2026, 3, 10)
        assert fechas[0]["titulo"] == "Inaugural"

    def test_titulo_enumerado(self):
        """Títulos incluyen #N."""
        fechas = self._call(
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=3,
            fecha_unica=None,
            titulo="Clase",
            hora="18:00",
        )
        assert fechas[0]["titulo"] == "Clase #1"
        assert fechas[2]["titulo"] == "Clase #3"

    def test_hora_preservada(self):
        """hora se mantiene en cada instancia."""
        fechas = self._call(
            fecha_inicio=date(2026, 3, 10),
            cant_semanas=2,
            fecha_unica=None,
            titulo="Test",
            hora="20:30",
        )
        assert fechas[0]["hora"] == "20:30"
        assert fechas[1]["hora"] == "20:30"

    def test_cant_semanas_cero_sin_fecha_unica(self):
        """cant_semanas=0 con fecha_unica=None → error."""
        import inspect

        with pytest.raises(ValueError, match="Modo inválido"):
            self._call(
                fecha_inicio=date(2026, 3, 10),
                cant_semanas=0,
                fecha_unica=None,
                titulo="Test",
                hora="18:00",
            )


class TestGeneracionHTML:
    """HTML block generation — pure function."""

    def _make_instancia(self, **kwargs):
        class FakeInstancia:
            pass

        inst = FakeInstancia()
        defaults = {
            "fecha": date(2026, 3, 10),
            "hora": "18:00",
            "titulo": "Clase #1",
            "estado": "Realizado",
            "meet_url": None,
            "video_url": None,
        }
        for k, v in {**defaults, **kwargs}.items():
            setattr(inst, k, v)
        return inst

    def test_genera_html_con_encabezado(self):
        from app.services.encuentro_service import generar_html_instancias

        instancias = [self._make_instancia()]
        html = generar_html_instancias("Programación I", instancias)
        assert "<h3>Encuentros de Programación I</h3>" in html
        assert "Clase #1" in html
        assert "10/03" in html  # DD/MM format
        assert "18:00" in html

    def test_incluye_enlace_meet(self):
        from app.services.encuentro_service import generar_html_instancias

        instancias = [self._make_instancia(
            meet_url="https://meet.google.com/abc",
        )]
        html = generar_html_instancias("PROG1", instancias)
        assert 'href="https://meet.google.com/abc"' in html

    def test_incluye_enlace_video(self):
        from app.services.encuentro_service import generar_html_instancias

        instancias = [self._make_instancia(
            video_url="https://youtube.com/watch?v=test",
        )]
        html = generar_html_instancias("PROG1", instancias)
        assert 'href="https://youtube.com/watch?v=test"' in html
        assert "Grabación" in html

    def test_html_escape_urls(self):
        from app.services.encuentro_service import generar_html_instancias

        # Malicious URL with XSS — quotes must be escaped to prevent
        # attribute injection
        instancias = [self._make_instancia(
            meet_url='javascript:alert("xss")',
        )]
        html = generar_html_instancias("PROG1", instancias)
        # Quotes should be escaped to &quot;, preventing attribute breakout
        assert "&quot;" in html
        # The href value must be properly quoted
        assert 'href="' in html

    def test_multiple_instancias(self):
        from app.services.encuentro_service import generar_html_instancias

        instancias = [
            self._make_instancia(fecha=date(2026, 3, 10), titulo="Clase #1"),
            self._make_instancia(fecha=date(2026, 3, 17), titulo="Clase #2"),
        ]
        html = generar_html_instancias("PROG1", instancias)
        assert "Clase #1" in html
        assert "Clase #2" in html
        assert html.count("<li>") == 2


class TestExportCSV:
    """CSV export — pure function."""

    def test_genera_csv_con_encabezados(self):
        from app.services.guardia_service import exportar_csv_guardias
        import csv, io

        data = [
            {
                "dia": "Lunes",
                "horario": "14:00-14:45",
                "estado": "Pendiente",
                "materia": "Programación I",
                "carrera": "TSDS",
                "cohorte": "2026",
                "comentarios": "Consulta TP2",
                "creada_at": datetime(2026, 6, 19, 10, 0, 0),
            }
        ]
        csv_str = exportar_csv_guardias(data)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["dia"] == "Lunes"
        assert rows[0]["materia"] == "Programación I"

    def test_csv_multiple_rows(self):
        from app.services.guardia_service import exportar_csv_guardias
        import csv, io

        data = [
            {"dia": "Lunes", "horario": "14:00", "estado": "Pendiente",
             "materia": "PROG1", "carrera": "TSDS", "cohorte": "2026",
             "comentarios": "", "creada_at": datetime(2026, 6, 19)},
            {"dia": "Martes", "horario": "15:00", "estado": "Realizada",
             "materia": "PROG1", "carrera": "TSDS", "cohorte": "2026",
             "comentarios": "OK", "creada_at": datetime(2026, 6, 20)},
        ]
        csv_str = exportar_csv_guardias(data)
        lines = csv_str.strip().split("\n")
        assert len(lines) == 3  # header + 2 data rows


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4 & 5 tests: Integration / E2E
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def enc_profesor_token(seed_data: dict) -> str:
    """JWT for profesor with encuentros:gestionar."""
    return create_access_token(data={
        "sub": str(seed_data["profesor_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


@pytest_asyncio.fixture
async def enc_coordinador_token(seed_data: dict) -> str:
    """JWT for coordinador with encuentros:gestionar."""
    return create_access_token(data={
        "sub": str(seed_data["coordinador_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


@pytest_asyncio.fixture
async def enc_no_perm_token(seed_data: dict) -> str:
    """JWT for user without encuentros:gestionar."""
    return create_access_token(data={
        "sub": str(seed_data["no_perm_user_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


class TestE2ESlots:
    """E2E: crear slot recurrente → listar → editar → HTML."""

    SLOTS_URL = "/api/encuentros/slots"
    INSTANCIAS_URL = "/api/encuentros/instancias"

    async def test_crear_slot_recurrente(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """POST /api/encuentros/slots recurrente → 201 + 15 instancias."""
        resp = await async_client.post(
            self.SLOTS_URL,
            json={
                "materia_id": str(seed_encuentros["materia_id"]),
                "titulo": "Clase de PROG1 TDD",
                "hora": "18:00",
                "dia_semana": "Lunes",
                "fecha_inicio": "2026-03-10",
                "cant_semanas": 15,
                "meet_url": "https://meet.google.com/tdd-test",
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["total_instancias"] == 15
        assert len(body["instancias"]) == 15
        assert body["slot"]["titulo"] == "Clase de PROG1 TDD"
        first_fecha = body["instancias"][0]["fecha"]
        assert "2026-03-10" in first_fecha

    async def test_crear_slot_fecha_unica(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """POST /api/encuentros/slots fecha única → 201 + 1 instancia."""
        resp = await async_client.post(
            self.SLOTS_URL,
            json={
                "materia_id": str(seed_encuentros["materia_id"]),
                "titulo": "Clase Inaugural TDD",
                "hora": "18:00",
                "dia_semana": "Lunes",
                "fecha_inicio": "2026-03-10",
                "cant_semanas": 0,
                "fecha_unica": "2026-03-10",
                "meet_url": "https://meet.google.com/inaugural",
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["total_instancias"] == 1
        assert len(body["instancias"]) == 1
        assert body["instancias"][0]["estado"] == "Programado"

    async def test_crear_slot_modo_ambiguo_422(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """Modo ambiguo → 422."""
        resp = await async_client.post(
            self.SLOTS_URL,
            json={
                "materia_id": str(seed_encuentros["materia_id"]),
                "titulo": "Invalido",
                "hora": "18:00",
                "dia_semana": "Lunes",
                "fecha_inicio": "2026-03-10",
                "cant_semanas": 0,
                # fecha_unica omitted → inválido
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 422, resp.text

    async def test_editar_instancia(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """PATCH /api/encuentros/instancias/{id} → 200."""
        inst_id = seed_encuentros["instancia_ids"][0]
        resp = await async_client.patch(
            f"{self.INSTANCIAS_URL}/{inst_id}",
            json={
                "estado": "Realizado",
                "video_url": "https://youtube.com/watch?v=test",
                "comentario": "Buena clase",
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["estado"] == "Realizado"
        assert body["video_url"] == "https://youtube.com/watch?v=test"
        assert body["comentario"] == "Buena clase"

    async def test_editar_instancia_no_afecta_otras(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """Editar instancia A no afecta B (RN-14)."""
        inst_a = seed_encuentros["instancia_ids"][0]
        inst_b = seed_encuentros["instancia_ids"][1]

        resp_a = await async_client.patch(
            f"{self.INSTANCIAS_URL}/{inst_a}",
            json={"estado": "Realizado"},
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp_a.status_code == 200

        resp_b = await async_client.get(
            f"{self.INSTANCIAS_URL}?materia_id={seed_encuentros['materia_id']}",
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp_b.status_code == 200
        items = resp_b.json()["items"]
        for item in items:
            if item["id"] == str(inst_b):
                assert item["estado"] == "Programado"

    async def test_listar_instancias_con_filtros(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """GET /api/encuentros/instancias con filtros."""
        resp = await async_client.get(
            f"{self.INSTANCIAS_URL}?materia_id={seed_encuentros['materia_id']}"
            "&desde=2026-03-01&hasta=2026-04-01",
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3  # week 1, 2, 3 in March
        assert len(body["items"]) == body["total"]

    async def test_generar_html(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """GET /api/encuentros/instancias/{id}/html → returns HTML."""
        inst_id = seed_encuentros["instancia_ids"][0]
        resp = await async_client.get(
            f"{self.INSTANCIAS_URL}/{inst_id}/html",
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "html" in body
        assert "<h3>" in body["html"]
        assert "Clase" in body["html"]

    async def test_listar_slots(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """GET /api/encuentros/slots."""
        resp = await async_client.get(
            f"{self.SLOTS_URL}?materia_id={seed_encuentros['materia_id']}",
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert len(body["items"]) >= 1


class TestE2EGuardias:
    """E2E: crear guardia → listar → editar → export."""

    GUARDIAS_URL = "/api/guardias"

    async def test_crear_guardia(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """POST /api/guardias → 201."""
        resp = await async_client.post(
            self.GUARDIAS_URL,
            json={
                "asignacion_id": str(seed_encuentros["asignacion_prof_id"]),
                "materia_id": str(seed_encuentros["materia_id"]),
                "carrera_id": str(seed_encuentros["carrera_id"]),
                "cohorte_id": str(seed_encuentros["cohorte_id"]),
                "dia": "Miercoles",
                "horario": "16:00-16:45",
                "comentarios": "Nueva guardia",
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["estado"] == "Pendiente"
        assert body["dia"] == "Miercoles"

    async def test_listar_guardias(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """GET /api/guardias → 200."""
        resp = await async_client.get(
            f"{self.GUARDIAS_URL}?materia_id={seed_encuentros['materia_id']}&estado=Pendiente",
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for item in body["items"]:
            assert item["estado"] == "Pendiente"

    async def test_editar_guardia(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """PATCH /api/guardias/{id} → 200."""
        guardia_id = seed_encuentros["guardia_id"]
        resp = await async_client.patch(
            f"{self.GUARDIAS_URL}/{guardia_id}",
            json={
                "estado": "Realizada",
                "comentarios": "Se resolvieron dudas",
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["estado"] == "Realizada"
        assert body["comentarios"] == "Se resolvieron dudas"

    async def test_export_csv(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """GET /api/guardias/export → CSV."""
        resp = await async_client.get(
            f"{self.GUARDIAS_URL}/export?materia_id={seed_encuentros['materia_id']}",
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/csv")
        assert "dia" in resp.text
        assert "Lunes" in resp.text

    async def test_crear_guardia_422(
        self, async_client: AsyncClient, seed_encuentros: dict, enc_profesor_token: str,
    ):
        """POST /api/guardias sin materia_id → 422."""
        resp = await async_client.post(
            self.GUARDIAS_URL,
            json={
                "asignacion_id": str(seed_encuentros["asignacion_prof_id"]),
                "dia": "Lunes",
                "horario": "14:00",
                # missing materia_id, carrera_id, cohorte_id
            },
            headers={"Authorization": f"Bearer {enc_profesor_token}"},
        )
        assert resp.status_code == 422, resp.text


class TestPermissions:
    """403 permission tests."""

    async def test_no_token_returns_403(self, async_client: AsyncClient):
        """Endpoints sin token → 403."""
        endpoints = [
            ("POST", "/api/encuentros/slots"),
            ("PATCH", f"/api/encuentros/instancias/{uuid.uuid4()}"),
            ("GET", "/api/encuentros/instancias"),
            ("GET", "/api/encuentros/slots"),
            ("POST", "/api/guardias"),
            ("GET", "/api/guardias"),
            ("GET", "/api/guardias/export"),
        ]
        for method, url in endpoints:
            resp = await async_client.request(method, url)
            assert resp.status_code == 403, f"{method} {url} should be 403"

    async def test_no_perm_returns_403(
        self, async_client: AsyncClient, enc_no_perm_token: str,
    ):
        """User without encuentros:gestionar → 403."""
        resp = await async_client.post(
            "/api/encuentros/slots",
            json={
                "materia_id": str(uuid.uuid4()),
                "titulo": "Test",
                "hora": "18:00",
                "dia_semana": "Lunes",
                "fecha_inicio": "2026-03-10",
                "cant_semanas": 1,
            },
            headers={"Authorization": f"Bearer {enc_no_perm_token}"},
        )
        assert resp.status_code == 403

    async def test_no_perm_guardia_returns_403(
        self, async_client: AsyncClient, enc_no_perm_token: str,
    ):
        """User without guardias:gestionar → 403."""
        resp = await async_client.post(
            "/api/guardias",
            json={
                "asignacion_id": str(uuid.uuid4()),
                "materia_id": str(uuid.uuid4()),
                "carrera_id": str(uuid.uuid4()),
                "cohorte_id": str(uuid.uuid4()),
                "dia": "Lunes",
                "horario": "14:00",
            },
            headers={"Authorization": f"Bearer {enc_no_perm_token}"},
        )
        assert resp.status_code == 403
