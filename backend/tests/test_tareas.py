"""Tests for Tareas Internas module (C-16).

Strict TDD: tests written BEFORE implementation.
"""

from __future__ import annotations

import uuid

import pytest_asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Model tests (Tasks 1.1 & 1.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEstadoTareaEnum:
    """EstadoTarea enum — values must match design."""

    def test_enum_values(self):
        from app.models.tarea import EstadoTarea
        assert EstadoTarea.Pendiente.value == "Pendiente"
        assert EstadoTarea.EnProgreso.value == "EnProgreso"
        assert EstadoTarea.Resuelta.value == "Resuelta"
        assert EstadoTarea.Cancelada.value == "Cancelada"

    def test_enum_is_string_enum(self):
        from app.models.tarea import EstadoTarea
        import enum
        assert issubclass(EstadoTarea, str)
        assert issubclass(EstadoTarea, enum.Enum)


class TestTareaModel:
    """Tarea model — structural tests."""

    def test_tablename(self):
        from app.models.tarea import Tarea
        assert Tarea.__tablename__ == "tarea"

    def test_fields_exist(self):
        from app.models.tarea import Tarea
        cols = {c.name for c in Tarea.__table__.columns}
        assert "tenant_id" in cols
        assert "materia_id" in cols
        assert "asignado_a" in cols
        assert "asignado_por" in cols
        assert "estado" in cols
        assert "descripcion" in cols
        assert "contexto_id" in cols
        assert "deleted_at" in cols  # Soft delete

    def test_inherits_soft_delete(self):
        from app.models.tarea import Tarea
        assert hasattr(Tarea, "deleted_at")

    def test_inherits_tenant_scope(self):
        from app.models.tarea import Tarea
        assert hasattr(Tarea, "tenant_id")


class TestComentarioTareaModel:
    """ComentarioTarea model — structural tests."""

    def test_tablename(self):
        from app.models.comentario_tarea import ComentarioTarea
        assert ComentarioTarea.__tablename__ == "comentario_tarea"

    def test_fields_exist(self):
        from app.models.comentario_tarea import ComentarioTarea
        cols = {c.name for c in ComentarioTarea.__table__.columns}
        assert "tarea_id" in cols
        assert "autor_id" in cols
        assert "texto" in cols
        assert "creado_at" in cols
        assert "created_at" in cols
        assert "tenant_id" in cols

    def test_no_soft_delete(self):
        """ComentarioTarea is an audit trail — no soft delete."""
        from app.models.comentario_tarea import ComentarioTarea
        assert "deleted_at" not in {c.name for c in ComentarioTarea.__table__.columns}
        assert not hasattr(ComentarioTarea, "deleted_at")


# ═══════════════════════════════════════════════════════════════════════════════
# Fixture: seed_tareas
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_tareas() -> dict:
    """Seed: tenant + 2 users + materia + permisos for tareas module."""
    from uuid import uuid4 as _uuid4

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
        tenant = Tenant(nombre="Tareas Tenant", codigo=f"TA{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        # ── Users ───────────────────────────────────────────────────
        prof = User(
            tenant_id=tenant.id, email=f"prof-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("ProfPass123!"), display_name="Profesor A",
            is_active=True,
        )
        session.add(prof)
        await session.flush()

        otro = User(
            tenant_id=tenant.id, email=f"otro-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("OtroPass123!"), display_name="Profesor B",
            is_active=True,
        )
        session.add(otro)
        await session.flush()

        no_perm = User(
            tenant_id=tenant.id, email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"), display_name="Sin Permiso",
            is_active=True,
        )
        session.add(no_perm)
        await session.flush()

        # ── Roles ───────────────────────────────────────────────────
        rol_prof = Role(
            tenant_id=tenant.id, codigo="PROFESOR", nombre="Profesor",
        )
        session.add(rol_prof)
        await session.flush()

        rol_coord = Role(
            tenant_id=tenant.id, codigo="COORDINADOR", nombre="Coordinador",
        )
        session.add(rol_coord)
        await session.flush()

        from datetime import date

        # Assign PROFESOR role
        session.add(UserRole(user_id=prof.id, role_id=rol_prof.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        session.add(UserRole(user_id=otro.id, role_id=rol_prof.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        session.add(UserRole(user_id=no_perm.id, role_id=rol_prof.id, tenant_id=tenant.id, desde=date(2024, 1, 1)))
        await session.flush()

        # ── Permission tareas:gestionar ──────────────────────────────
        perm = Permission(
            id=uuid.uuid4(), tenant_id=tenant.id,
            codigo="tareas:gestionar", descripcion="Gestionar tareas",
        )
        session.add(perm)
        await session.flush()

        session.add(RolePermission(
            id=uuid.uuid4(), role_id=rol_prof.id, permission_id=perm.id,
        ))
        session.add(RolePermission(
            id=uuid.uuid4(), role_id=rol_coord.id, permission_id=perm.id,
        ))
        await session.flush()

        # ── Academic data: carrera + cohorte + materia ───────────────
        carrera = Carrera(tenant_id=tenant.id, codigo="TUP", nombre="Tecnicatura")
        session.add(carrera)
        await session.flush()

        cohorte = Cohorte(
            tenant_id=tenant.id, carrera_id=carrera.id,
            nombre="2025-A", anio=2025,
            vig_desde=date(2025, 1, 1),
        )
        session.add(cohorte)
        await session.flush()

        materia = Materia(
            tenant_id=tenant.id, codigo="PROG1", nombre="Programacion I",
        )
        session.add(materia)
        await session.flush()

        await session.commit()

        data["tenant_id"] = tenant.id
        data["prof_id"] = prof.id
        data["otro_id"] = otro.id
        data["no_perm_id"] = no_perm.id
        data["materia_id"] = materia.id
        data["cohorte_id"] = cohorte.id

    await engine.dispose()
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: Repository tests (Tasks 2.1 & 2.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTareaRepository:
    """TareaRepository — CRUD, list_por_asignado, list_con_filtros, ILIKE."""

    @pytest_asyncio.fixture
    async def repo(self, seed_tareas):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.core.database import Base
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._engine = engine
        self._factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return seed_tareas

    async def _make_repo(self, session):
        from app.repositories.tarea_repository import TareaRepository
        from app.repositories.tarea_repository import ComentarioTareaRepository
        return TareaRepository, ComentarioTareaRepository

    async def test_create_and_get(self, repo):
        """Create a tarea and retrieve by id."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])
            tarea = await r.create(
                materia_id=repo["materia_id"],
                asignado_a=repo["prof_id"],
                asignado_por=repo["otro_id"],
                estado="Pendiente",
                descripcion="Revisar entregas del TP2",
            )
            await session.commit()

            fetched = await r.get(tarea.id)
            assert fetched is not None
            assert fetched.descripcion == "Revisar entregas del TP2"
            assert fetched.estado == "Pendiente"
            assert fetched.asignado_a == repo["prof_id"]
            assert fetched.asignado_por == repo["otro_id"]
            assert fetched.materia_id == repo["materia_id"]
        await engine.dispose()

    async def test_list_por_asignado(self, repo):
        """list_por_asignado returns only tasks for the given user."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])

            # Create task for prof
            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Tarea de prof", estado="Pendiente",
            )
            # Create task for otro
            await r.create(
                asignado_a=repo["otro_id"], asignado_por=repo["prof_id"],
                descripcion="Tarea de otro", estado="Pendiente",
            )
            await session.commit()

            prof_tasks = await r.list_por_asignado(repo["prof_id"])
            assert len(prof_tasks) == 1
            assert prof_tasks[0].descripcion == "Tarea de prof"

            otro_tasks = await r.list_por_asignado(repo["otro_id"])
            assert len(otro_tasks) == 1
            assert otro_tasks[0].descripcion == "Tarea de otro"
        await engine.dispose()

    async def test_list_por_asignado_con_filtro_estado(self, repo):
        """list_por_asignado with estado filter."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])

            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Pendiente task", estado="Pendiente",
            )
            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Resuelta task", estado="Resuelta",
            )
            await session.commit()

            pendientes = await r.list_por_asignado(repo["prof_id"], estado="Pendiente")
            assert len(pendientes) == 1
            assert pendientes[0].descripcion == "Pendiente task"

            resueltas = await r.list_por_asignado(repo["prof_id"], estado="Resuelta")
            assert len(resueltas) == 1
        await engine.dispose()

    async def test_list_por_asignado_con_filtro_materia(self, repo):
        """list_por_asignado with materia_id filter."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])

            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Con materia", estado="Pendiente",
                materia_id=repo["materia_id"],
            )
            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Sin materia", estado="Pendiente",
            )
            await session.commit()

            result = await r.list_por_asignado(
                repo["prof_id"], materia_id=repo["materia_id"],
            )
            assert len(result) == 1
            assert result[0].descripcion == "Con materia"
        await engine.dispose()

    async def test_list_con_filtros_admin(self, repo):
        """Admin list with combined filters and ILIKE search."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])

            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Preparar informe de atrasados", estado="Pendiente",
            )
            await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Corregir parcial", estado="Resuelta",
            )
            await r.create(
                asignado_a=repo["otro_id"], asignado_por=repo["prof_id"],
                descripcion="Informe final de cohorte", estado="Pendiente",
            )
            await session.commit()

            # All
            all_tasks = await r.list_con_filtros(tenant_id=repo["tenant_id"])
            assert len(all_tasks) == 3

            # Filter by estado
            pendientes = await r.list_con_filtros(
                tenant_id=repo["tenant_id"], estado="Pendiente",
            )
            assert len(pendientes) == 2

            # ILIKE search
            informe = await r.list_con_filtros(
                tenant_id=repo["tenant_id"], q="informe",
            )
            assert len(informe) == 2  # "Preparar informe..." + "Informe final..."
            descs = {t.descripcion for t in informe}
            assert "Preparar informe de atrasados" in descs
            assert "Informe final de cohorte" in descs

            # Combined: estado + ILIKE
            combined = await r.list_con_filtros(
                tenant_id=repo["tenant_id"], estado="Pendiente", q="informe",
            )
            assert len(combined) == 2  # both Pendiente tareas contain "informe"
            descs_c = {t.descripcion for t in combined}
            assert "Preparar informe de atrasados" in descs_c
            assert "Informe final de cohorte" in descs_c
        await engine.dispose()

    async def test_update_estado(self, repo):
        """Update tarea estado."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])
            tarea = await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="Cambiar estado", estado="Pendiente",
            )
            await session.commit()

            updated = await r.update(tarea.id, estado="EnProgreso")
            assert updated is not None
            assert updated.estado == "EnProgreso"
        await engine.dispose()

    async def test_soft_delete(self, repo):
        """Soft delete sets deleted_at."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = TareaRepository(session=session, tenant_id=repo["tenant_id"])
            tarea = await r.create(
                asignado_a=repo["prof_id"], asignado_por=repo["otro_id"],
                descripcion="A borrar", estado="Pendiente",
            )
            await session.commit()

            deleted = await r.soft_delete(tarea.id)
            assert deleted is True

            fetched = await r.get(tarea.id)
            assert fetched is None  # excluded by _exclude_deleted
        await engine.dispose()


class TestComentarioTareaRepository:
    """ComentarioTareaRepository — create, list_por_tarea."""

    async def test_create_and_list(self, seed_tareas):
        """Create comentario and list by tarea."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.tarea_repository import TareaRepository, ComentarioTareaRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            tr = TareaRepository(session=session, tenant_id=seed_tareas["tenant_id"])
            tarea = await tr.create(
                asignado_a=seed_tareas["prof_id"], asignado_por=seed_tareas["otro_id"],
                descripcion="Tarea con comentarios", estado="Pendiente",
            )
            await session.commit()

            cr = ComentarioTareaRepository(session=session, tenant_id=seed_tareas["tenant_id"])
            c1 = await cr.create(
                tarea_id=tarea.id, autor_id=seed_tareas["prof_id"],
                texto="Primer comentario",
            )
            c2 = await cr.create(
                tarea_id=tarea.id, autor_id=seed_tareas["otro_id"],
                texto="Segundo comentario",
            )
            await session.commit()

            comentarios = await cr.list_por_tarea(tarea.id)
            assert len(comentarios) == 2
            assert comentarios[0].texto == "Primer comentario"
            assert comentarios[1].texto == "Segundo comentario"
            # Verify ASC order by creado_at
            assert comentarios[0].creado_at <= comentarios[1].creado_at
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Schema tests (Task 3.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTareaSchemas:
    """Schema validation and serialization."""

    def test_crear_request_extra_forbid(self):
        """TareaCrearRequest rejects unknown fields."""
        from pydantic import ValidationError
        from app.schemas.tareas import TareaCrearRequest
        try:
            TareaCrearRequest(
                asignado_a=uuid.uuid4(), descripcion="test",
                campo_inexistente="boom",
            )
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass

    def test_crear_request_required_fields(self):
        """TareaCrearRequest requires asignado_a and descripcion."""
        from pydantic import ValidationError
        from app.schemas.tareas import TareaCrearRequest
        try:
            TareaCrearRequest()  # type: ignore[call-arg]
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass

    def test_estado_update_extra_forbid(self):
        """TareaEstadoUpdateRequest rejects unknown fields."""
        from pydantic import ValidationError
        from app.schemas.tareas import TareaEstadoUpdateRequest
        try:
            TareaEstadoUpdateRequest(estado="Pendiente", extra="no")
            assert False
        except ValidationError:
            pass

    def test_response_from_attributes(self):
        """TareaResponse is configured for ORM compatibility."""
        from app.schemas.tareas import TareaResponse
        assert TareaResponse.model_config.get("from_attributes") is True


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4: Unit tests — state machine (Task 6.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTransicionesEstado:
    """Pure unit tests for state machine validation."""

    def _validar(self, actual, nueva):
        from app.services.tarea_service import _validar_transicion
        _validar_transicion(actual, nueva)

    def test_pendiente_a_enprogreso_valida(self):
        self._validar("Pendiente", "EnProgreso")  # no exception

    def test_pendiente_a_cancelada_valida(self):
        self._validar("Pendiente", "Cancelada")  # no exception

    def test_enprogreso_a_resuelta_valida(self):
        self._validar("EnProgreso", "Resuelta")  # no exception

    def test_enprogreso_a_cancelada_valida(self):
        self._validar("EnProgreso", "Cancelada")  # no exception

    def test_resuelta_a_pendiente_invalida(self):
        from fastapi import HTTPException
        try:
            self._validar("Resuelta", "Pendiente")
            assert False, "Should have raised HTTPException 409"
        except HTTPException as e:
            assert e.status_code == 409

    def test_cancelada_a_enprogreso_invalida(self):
        from fastapi import HTTPException
        try:
            self._validar("Cancelada", "EnProgreso")
            assert False, "Should have raised HTTPException 409"
        except HTTPException as e:
            assert e.status_code == 409

    def test_pendiente_a_resuelta_invalida(self):
        from fastapi import HTTPException
        try:
            self._validar("Pendiente", "Resuelta")
            assert False, "Should have raised HTTPException 409"
        except HTTPException as e:
            assert e.status_code == 409
