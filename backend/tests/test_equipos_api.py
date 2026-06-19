"""E2E API tests for /api/equipos endpoints.

Covers E1-E6 scenarios: mi-equipo, gestionar, asignacion-masiva,
clonar, vigencia, exportar. Multi-tenant isolation and auth guards.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User

from .conftest import TEST_SETTINGS


# ── Shared seed fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_data(async_client: AsyncClient) -> dict:
    """Seed tenant + admin user with equipos:gestionar permission + academic data.

    Also creates a second target user (docente) for assignment tests.
    """
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Equipos Tenant", codigo=f"EQ{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        # Admin user (has equipos:gestionar)
        admin = User(
            tenant_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("AdminPass123!"),
            display_name="Admin User",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        # Docente user (gets assignments)
        docente = User(
            tenant_id=tenant.id,
            email=f"docente-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("DocentePass123!"),
            display_name="Docente Garcia",
            is_active=True,
        )
        session.add(docente)
        await session.flush()

        # Second docente for multi-tenant tests
        otro_docente = User(
            tenant_id=tenant.id,
            email=f"otro-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("OtroPass123!"),
            display_name="Otro Docente",
            is_active=True,
        )
        session.add(otro_docente)
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
            vig_hasta=date(2026, 12, 31),
        )
        session.add(cohorte)
        await session.flush()

        cohorte2 = Cohorte(
            tenant_id=tenant.id,
            carrera_id=carrera.id,
            nombre="2026-B",
            anio=2026,
            vig_desde=date(2026, 7, 1),
            vig_hasta=date(2026, 12, 31),
        )
        session.add(cohorte2)
        await session.flush()

        materia = Materia(
            tenant_id=tenant.id, codigo="PROG1", nombre="Programacion I"
        )
        session.add(materia)
        await session.flush()

        # Role with equipos:gestionar
        role = Role(tenant_id=tenant.id, nombre="Equipos Admin", codigo="EQADMIN")
        session.add(role)
        await session.flush()

        for perm_codigo in ["equipos:gestionar"]:
            perm = Permission(tenant_id=tenant.id, codigo=perm_codigo)
            session.add(perm)
            await session.flush()
            rp = RolePermission(role_id=role.id, permission_id=perm.id)
            session.add(rp)
            await session.flush()

        # Assign admin role to admin user
        ur = UserRole(
            tenant_id=tenant.id,
            user_id=admin.id,
            role_id=role.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur)
        await session.flush()

        # Basic role for docente (no equipos:gestionar)
        role_basic = Role(tenant_id=tenant.id, nombre="Basic", codigo="BASIC")
        session.add(role_basic)
        await session.flush()

        perm_basic = Permission(tenant_id=tenant.id, codigo="basico:leer")
        session.add(perm_basic)
        await session.flush()
        rp_basic = RolePermission(role_id=role_basic.id, permission_id=perm_basic.id)
        session.add(rp_basic)
        await session.flush()

        ur_docente = UserRole(
            tenant_id=tenant.id,
            user_id=docente.id,
            role_id=role_basic.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur_docente)
        await session.flush()

        data = {
            "tenant_id": tenant.id,
            "admin_id": admin.id,
            "docente_id": docente.id,
            "otro_docente_id": otro_docente.id,
            "carrera_id": carrera.id,
            "cohorte_id": cohorte.id,
            "cohorte2_id": cohorte2.id,
            "materia_id": materia.id,
        }
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def seed_other_tenant(async_client: AsyncClient) -> dict:
    """Seed a different tenant for multi-tenant isolation tests."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Other Equipos", codigo=f"OTE{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        admin = User(
            tenant_id=tenant.id,
            email=f"other-admin-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("OtherPass123!"),
            display_name="Other Admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        role = Role(tenant_id=tenant.id, nombre="Other Admin", codigo="OTHERADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tenant.id, codigo="equipos:gestionar")
        session.add(perm)
        await session.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp)
        await session.flush()

        ur = UserRole(
            tenant_id=tenant.id,
            user_id=admin.id,
            role_id=role.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur)
        await session.flush()

        data = {
            "email": admin.email,
            "password": "OtherPass123!",
            "tenant_id": tenant.id,
            "user_id": admin.id,
        }
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def seed_asignaciones(seed_data: dict) -> dict:
    """Create test assignments for the docente user.

    Returns seed_data enriched with assignment data.
    """
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data = dict(seed_data)

    async with factory() as session:
        from app.models.asignacion import Asignacion

        # Create a responsable user
        responsable = User(
            tenant_id=data["tenant_id"],
            email=f"resp-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("RespPass123!"),
            display_name="Juan Perez",
            is_active=True,
        )
        session.add(responsable)
        await session.flush()

        # Assignment 1: vigente, PROFESOR, with responsable
        a1 = Asignacion(
            tenant_id=data["tenant_id"],
            usuario_id=data["docente_id"],
            rol="PROFESOR",
            materia_id=data["materia_id"],
            carrera_id=data["carrera_id"],
            cohorte_id=data["cohorte_id"],
            comisiones=["A", "B"],
            responsable_id=responsable.id,
            desde=date(2026, 3, 1),
        )
        session.add(a1)
        await session.flush()

        # Assignment 2: vigente, TUTOR (different role)
        a2 = Asignacion(
            tenant_id=data["tenant_id"],
            usuario_id=data["docente_id"],
            rol="TUTOR",
            materia_id=data["materia_id"],
            carrera_id=data["carrera_id"],
            cohorte_id=data["cohorte_id"],
            comisiones=["C"],
            desde=date(2026, 3, 1),
            hasta=date(2026, 12, 31),
        )
        session.add(a2)
        await session.flush()

        # Assignment 3: vencida (for testing vigentes_only)
        a3 = Asignacion(
            tenant_id=data["tenant_id"],
            usuario_id=data["docente_id"],
            rol="PROFESOR",
            materia_id=data["materia_id"],
            carrera_id=data["carrera_id"],
            cohorte_id=data["cohorte_id"],
            comisiones=["D"],
            desde=date(2024, 1, 1),
            hasta=date(2024, 6, 30),
        )
        session.add(a3)
        await session.flush()

        # Assignment 4: for otro docente (should not appear for docente)
        a4 = Asignacion(
            tenant_id=data["tenant_id"],
            usuario_id=data["otro_docente_id"],
            rol="PROFESOR",
            materia_id=data["materia_id"],
            carrera_id=data["carrera_id"],
            cohorte_id=data["cohorte_id"],
            comisiones=["X"],
            desde=date(2026, 3, 1),
        )
        session.add(a4)
        await session.flush()

        data["asignacion_ids"] = [a1.id, a2.id, a3.id, a4.id]
        data["responsable_id"] = responsable.id

        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def auth_token(seed_data: dict) -> str:
    """Generate a valid JWT for the admin user (has equipos:gestionar)."""
    return create_access_token(
        data={
            "sub": str(seed_data["admin_id"]),
            "tenant_id": str(seed_data["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def docente_token(seed_data: dict) -> str:
    """Generate a valid JWT for the docente user (no equipos:gestionar)."""
    return create_access_token(
        data={
            "sub": str(seed_data["docente_id"]),
            "tenant_id": str(seed_data["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def other_auth_token(seed_other_tenant: dict) -> str:
    """Generate a valid JWT for the other tenant admin."""
    return create_access_token(
        data={
            "sub": str(seed_other_tenant["user_id"]),
            "tenant_id": str(seed_other_tenant["tenant_id"]),
        }
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestMiEquipo:
    """GET /api/equipos/mi-equipo — E1: docente views their team."""

    async def test_mi_equipo_returns_vigentes(
        self, async_client: AsyncClient, docente_token: str, seed_asignaciones: dict
    ):
        """Docente sees only their vigentes assignments, not vencidas."""
        resp = await async_client.get(
            "/api/equipos/mi-equipo",
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Should return 2 vigentes (PROFESOR + TUTOR), not the vencida one
        assert body["total"] == 2
        items = body["items"]
        roles = {item["rol"] for item in items}
        assert "PROFESOR" in roles
        assert "TUTOR" in roles

    async def test_mi_equipo_does_not_see_other_docentes(
        self, async_client: AsyncClient, docente_token: str, seed_asignaciones: dict
    ):
        """Docente does not see other docente's assignments."""
        resp = await async_client.get(
            "/api/equipos/mi-equipo",
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["usuario"]["nombre"] == "Docente Garcia"

    async def test_mi_equipo_no_auth_returns_403(
        self, async_client: AsyncClient
    ):
        """GET /mi-equipo without token returns 403."""
        resp = await async_client.get("/api/equipos/mi-equipo")
        assert resp.status_code == 403

    async def test_mi_equipo_empty_for_new_user(
        self, async_client: AsyncClient, seed_data: dict
    ):
        """User with no assignments gets empty list."""
        # Create a user with no asignaciones
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            user = User(
                tenant_id=seed_data["tenant_id"],
                email=f"empty-{uuid.uuid4().hex[:8]}@test.com",
                password_hash=hash_password("Empty123!"),
                display_name="Empty User",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            await session.commit()

        token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(seed_data["tenant_id"]),
            }
        )
        await engine.dispose()

        resp = await async_client.get(
            "/api/equipos/mi-equipo",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0


class TestListEquipos:
    """GET /api/equipos — E2: gestionar tenant equipments."""

    async def test_list_all(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Returns all non-deleted assignments with expanded relations."""
        resp = await async_client.get(
            "/api/equipos",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3  # 3 non-deleted in tenant
        assert len(body["items"]) >= 3
        # Check expanded relations
        item = body["items"][0]
        assert "usuario" in item
        assert "materia" in item
        assert "carrera" in item
        assert "cohorte" in item
        assert "estado_vigencia" in item

    async def test_list_filter_by_rol(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Filter by rol returns only matching."""
        resp = await async_client.get(
            "/api/equipos?rol=TUTOR",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["rol"] == "TUTOR"

    async def test_list_filter_by_docente(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Filter by docente_id returns only their assignments."""
        resp = await async_client.get(
            f"/api/equipos?docente_id={seed_asignaciones['docente_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2  # 2 vigentes for docente
        for item in body["items"]:
            assert item["usuario"]["id"] == str(seed_asignaciones["docente_id"])

    async def test_list_search_by_q(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Text search matches user name or materia name."""
        resp = await async_client.get(
            "/api/equipos?q=Garcia",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    async def test_list_search_no_match(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Text search with no match returns empty."""
        resp = await async_client.get(
            "/api/equipos?q=ZZZZNOTEXISTENT",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    async def test_list_pagination(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Pagination limits and offsets correctly."""
        resp = await async_client.get(
            "/api/equipos?skip=0&limit=1",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 1


class TestAsignacionMasiva:
    """POST /api/equipos/asignacion-masiva — E3: bulk create."""

    async def test_bulk_create_success(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Create multiple assignments in one request."""
        resp = await async_client.post(
            "/api/equipos/asignacion-masiva",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "carrera_id": str(seed_data["carrera_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "comisiones": ["A"],
                "desde": "2026-03-01",
                "hasta": "2026-12-31",
                "asignaciones": [
                    {"usuario_id": str(seed_data["docente_id"]), "rol": "PROFESOR"},
                    {"usuario_id": str(seed_data["otro_docente_id"]), "rol": "TUTOR"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["creadas"] == 2
        assert len(body["items"]) == 2

    async def test_bulk_create_user_not_in_tenant(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Error if usuario_id does not exist in tenant."""
        resp = await async_client.post(
            "/api/equipos/asignacion-masiva",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "carrera_id": str(seed_data["carrera_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "comisiones": ["A"],
                "desde": "2026-03-01",
                "asignaciones": [
                    {"usuario_id": str(uuid.uuid4()), "rol": "PROFESOR"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400

    async def test_bulk_create_exceeds_limit(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Error if more than 200 assignments."""
        asignaciones = [
            {"usuario_id": str(seed_data["docente_id"]), "rol": "PROFESOR"}
            for _ in range(201)
        ]
        resp = await async_client.post(
            "/api/equipos/asignacion-masiva",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "carrera_id": str(seed_data["carrera_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "comisiones": ["A"],
                "desde": "2026-03-01",
                "asignaciones": asignaciones,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400


class TestClonarEquipo:
    """POST /api/equipos/clonar — E4: clone equipo between cohorts."""

    async def test_clone_success(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Clone vigentes assignments from one cohort to another."""
        data = seed_asignaciones
        resp = await async_client.post(
            "/api/equipos/clonar",
            json={
                "origen": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte_id"]),
                },
                "destino": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte2_id"]),
                },
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        # 3 vigentes assignments (PROFESOR+TUTOR for docente + PROFESOR for otro_docente)
        assert body["clonadas"] == 3
        assert len(body["items"]) == 3

    async def test_clone_respects_rn12(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Clone does not duplicate existing assignments (RN-12)."""
        data = seed_asignaciones

        # First clone
        resp1 = await async_client.post(
            "/api/equipos/clonar",
            json={
                "origen": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte_id"]),
                },
                "destino": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte2_id"]),
                },
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp1.status_code == 201

        # Second clone — should skip duplicates
        resp2 = await async_client.post(
            "/api/equipos/clonar",
            json={
                "origen": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte_id"]),
                },
                "destino": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte2_id"]),
                },
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["clonadas"] == 0

    async def test_clone_origen_destino_iguales(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Error if origen and destino are the same."""
        data = seed_asignaciones
        resp = await async_client.post(
            "/api/equipos/clonar",
            json={
                "origen": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte_id"]),
                },
                "destino": {
                    "materia_id": str(data["materia_id"]),
                    "carrera_id": str(data["carrera_id"]),
                    "cohorte_id": str(data["cohorte_id"]),
                },
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400


class TestVigencia:
    """PATCH /api/equipos/vigencia — E5: bulk update vigencia."""

    async def test_update_vigencia_success(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Update vigencia dates for matching assignments."""
        data = seed_asignaciones
        resp = await async_client.patch(
            "/api/equipos/vigencia",
            json={
                "materia_id": str(data["materia_id"]),
                "carrera_id": str(data["carrera_id"]),
                "cohorte_id": str(data["cohorte_id"]),
                "rol": "PROFESOR",
                "nuevo_hasta": "2026-12-31",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Only PROFESOR assignments (not TUTOR) should be updated
        assert body["actualizadas"] >= 1

    async def test_update_vigencia_past_date_requires_confirm(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Setting nuevo_desde in the past requires confirmar=true."""
        data = seed_asignaciones
        resp = await async_client.patch(
            "/api/equipos/vigencia",
            json={
                "materia_id": str(data["materia_id"]),
                "carrera_id": str(data["carrera_id"]),
                "cohorte_id": str(data["cohorte_id"]),
                "nuevo_desde": "2020-01-01",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400

    async def test_update_vigencia_past_date_with_confirm(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Setting nuevo_desde in the past works with confirmar=true."""
        data = seed_asignaciones
        resp = await async_client.patch(
            "/api/equipos/vigencia",
            json={
                "materia_id": str(data["materia_id"]),
                "carrera_id": str(data["carrera_id"]),
                "cohorte_id": str(data["cohorte_id"]),
                "nuevo_desde": "2020-01-01",
                "confirmar": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

    async def test_update_vigencia_no_filters_requires_confirm(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Updating all tenant without filters requires confirmar=true."""
        resp = await async_client.patch(
            "/api/equipos/vigencia",
            json={
                "nuevo_hasta": "2026-12-31",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400


class TestExportar:
    """GET /api/equipos/exportar — E6: CSV export."""

    async def test_export_csv_success(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Export returns CSV with correct headers."""
        resp = await async_client.get(
            "/api/equipos/exportar",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        # Check BOM (utf-8-sig)
        content = resp.content
        assert content[:3] == b"\xef\xbb\xbf"  # BOM
        # Check headers
        text = content.decode("utf-8-sig")
        lines = text.strip().split("\n")
        assert "id" in lines[0]
        assert "docente_nombre" in lines[0]
        assert "docente_email" in lines[0]

    async def test_export_csv_with_filters(
        self, async_client: AsyncClient, auth_token: str, seed_asignaciones: dict
    ):
        """Export respects filters."""
        data = seed_asignaciones
        resp = await async_client.get(
            f"/api/equipos/exportar?materia_id={data['materia_id']}&carrera_id={data['carrera_id']}&cohorte_id={data['cohorte_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        content = resp.content.decode("utf-8-sig")
        lines = content.strip().split("\n")
        # Header + data rows
        assert len(lines) >= 2


class TestPermisos:
    """Auth guard tests for equipos endpoints."""

    async def test_mi_equipo_no_auth(
        self, async_client: AsyncClient
    ):
        """GET /mi-equipo without auth returns 403."""
        resp = await async_client.get("/api/equipos/mi-equipo")
        assert resp.status_code == 403

    async def test_list_equipos_without_gestionar(
        self, async_client: AsyncClient, docente_token: str
    ):
        """User without equipos:gestionar gets 403 on GET /equipos."""
        resp = await async_client.get(
            "/api/equipos",
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 403

    async def test_asignacion_masiva_without_gestionar(
        self, async_client: AsyncClient, docente_token: str, seed_data: dict
    ):
        """User without equipos:gestionar gets 403 on POST asignacion-masiva."""
        resp = await async_client.post(
            "/api/equipos/asignacion-masiva",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "carrera_id": str(seed_data["carrera_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "comisiones": [],
                "desde": "2026-03-01",
                "asignaciones": [],
            },
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 403

    async def test_clonar_without_gestionar(
        self, async_client: AsyncClient, docente_token: str, seed_data: dict
    ):
        """User without equipos:gestionar gets 403 on POST clonar."""
        resp = await async_client.post(
            "/api/equipos/clonar",
            json={
                "origen": {
                    "materia_id": str(seed_data["materia_id"]),
                    "carrera_id": str(seed_data["carrera_id"]),
                    "cohorte_id": str(seed_data["cohorte_id"]),
                },
                "destino": {
                    "materia_id": str(seed_data["materia_id"]),
                    "carrera_id": str(seed_data["carrera_id"]),
                    "cohorte_id": str(seed_data["cohorte2_id"]),
                },
            },
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 403

    async def test_vigencia_without_gestionar(
        self, async_client: AsyncClient, docente_token: str, seed_data: dict
    ):
        """User without equipos:gestionar gets 403 on PATCH vigencia."""
        resp = await async_client.patch(
            "/api/equipos/vigencia",
            json={
                "nuevo_hasta": "2026-12-31",
                "confirmar": True,
            },
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 403

    async def test_exportar_without_gestionar(
        self, async_client: AsyncClient, docente_token: str
    ):
        """User without equipos:gestionar gets 403 on GET exportar."""
        resp = await async_client.get(
            "/api/equipos/exportar",
            headers={"Authorization": f"Bearer {docente_token}"},
        )
        assert resp.status_code == 403


class TestMultiTenant:
    """Multi-tenant isolation tests."""

    async def test_tenant_b_does_not_see_tenant_a_data(
        self,
        async_client: AsyncClient,
        auth_token: str,
        other_auth_token: str,
        seed_asignaciones: dict,
    ):
        """Tenant B admin sees empty list for equipos."""
        resp = await async_client.get(
            "/api/equipos",
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    async def test_mi_equipo_isolated(
        self,
        async_client: AsyncClient,
        other_auth_token: str,
        seed_asignaciones: dict,
    ):
        """Tenant B user sees empty mi-equipo."""
        resp = await async_client.get(
            "/api/equipos/mi-equipo",
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0


class TestBulkCreateExtra:
    """Additional edge cases for bulk create."""

    async def test_bulk_create_single(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Create a single assignment works."""
        resp = await async_client.post(
            "/api/equipos/asignacion-masiva",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "carrera_id": str(seed_data["carrera_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "comisiones": [],
                "desde": "2026-03-01",
                "asignaciones": [
                    {"usuario_id": str(seed_data["docente_id"]), "rol": "PROFESOR"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["creadas"] == 1
