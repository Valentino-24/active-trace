"""E2E API tests for /api/padron endpoints.

Covers E1-E6 scenarios: moodle sync, preview, import, vaciar,
list versiones, version detail. Multi-tenant isolation and auth guards.
"""

from __future__ import annotations

import io
import os
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.materia import Materia
from app.models.padron import EntradaPadron, VersionPadron
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User

from .conftest import TEST_SETTINGS

# ── Shared seed fixtures ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def seed_data(async_client: AsyncClient) -> dict:
    """Seed tenant + admin user with padron:importar + academic data + students."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Padron Tenant", codigo=f"PD{uuid.uuid4().hex[:4]}")
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

        # Student users for match testing
        student1 = User(
            tenant_id=tenant.id,
            email="student1@test.com",
            password_hash=hash_password("Stud123!"),
            display_name="Student One",
            is_active=True,
        )
        session.add(student1)
        await session.flush()

        student2 = User(
            tenant_id=tenant.id,
            email="student2@test.com",
            password_hash=hash_password("Stud456!"),
            display_name="Student Two",
            is_active=True,
        )
        session.add(student2)
        await session.flush()

        # PROFESOR user (for scope tests)
        profesor = User(
            tenant_id=tenant.id,
            email=f"prof-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("ProfPass123!"),
            display_name="Profesor Test",
            is_active=True,
        )
        session.add(profesor)
        await session.flush()

        # COORDINADOR user (for scope tests)
        coordinador = User(
            tenant_id=tenant.id,
            email=f"coord-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("CoordPass123!"),
            display_name="Coordinador Test",
            is_active=True,
        )
        session.add(coordinador)
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
            tenant_id=tenant.id, codigo="PROG1", nombre="Programacion I"
        )
        session.add(materia)
        await session.flush()

        materia2 = Materia(
            tenant_id=tenant.id, codigo="PROG2", nombre="Programacion II"
        )
        session.add(materia2)
        await session.flush()

        # Role with padron:importar
        role = Role(tenant_id=tenant.id, nombre="Padron Admin", codigo="PADRONADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tenant.id, codigo="padron:importar")
        session.add(perm)
        await session.flush()
        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp)
        await session.flush()

        # Assign admin role
        ur = UserRole(
            tenant_id=tenant.id,
            user_id=admin.id,
            role_id=role.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur)
        await session.flush()

        # PROFESOR role + padron:importar
        role_prof = Role(
            tenant_id=tenant.id, nombre="Profesor", codigo="PROFESOR"
        )
        session.add(role_prof)
        await session.flush()
        rp2 = RolePermission(role_id=role_prof.id, permission_id=perm.id)
        session.add(rp2)
        await session.flush()
        ur2 = UserRole(
            tenant_id=tenant.id,
            user_id=profesor.id,
            role_id=role_prof.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur2)
        await session.flush()

        # COORDINADOR role + padron:importar
        role_coord = Role(
            tenant_id=tenant.id, nombre="Coordinador", codigo="COORDINADOR"
        )
        session.add(role_coord)
        await session.flush()
        rp3 = RolePermission(role_id=role_coord.id, permission_id=perm.id)
        session.add(rp3)
        await session.flush()
        ur3 = UserRole(
            tenant_id=tenant.id,
            user_id=coordinador.id,
            role_id=role_coord.id,
            desde=date(2024, 1, 1),
        )
        session.add(ur3)
        await session.flush()

        # User without padron:importar (for 403 tests)
        no_perm_user = User(
            tenant_id=tenant.id,
            email=f"noperm-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("NoPerm123!"),
            display_name="No Perm User",
            is_active=True,
        )
        session.add(no_perm_user)
        await session.flush()

        data = {
            "tenant_id": tenant.id,
            "admin_id": admin.id,
            "profesor_id": profesor.id,
            "coordinador_id": coordinador.id,
            "no_perm_user_id": no_perm_user.id,
            "student1_id": student1.id,
            "student2_id": student2.id,
            "carrera_id": carrera.id,
            "cohorte_id": cohorte.id,
            "materia_id": materia.id,
            "materia2_id": materia2.id,
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
        tenant = Tenant(nombre="Other Tenant", codigo=f"OTH{uuid.uuid4().hex[:4]}")
        session.add(tenant)
        await session.flush()

        admin = User(
            tenant_id=tenant.id,
            email=f"other-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("OtherPass123!"),
            display_name="Other Admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        role = Role(tenant_id=tenant.id, nombre="Other Admin", codigo="OTHERADMIN")
        session.add(role)
        await session.flush()

        perm = Permission(tenant_id=tenant.id, codigo="padron:importar")
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
async def seed_padron_version(seed_data: dict) -> dict:
    """Create a VersionPadron with entries for list/detail tests."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data = dict(seed_data)

    async with factory() as session:
        version = VersionPadron(
            tenant_id=data["tenant_id"],
            materia_id=data["materia_id"],
            cohorte_id=data["cohorte_id"],
            cargado_por=data["admin_id"],
            activa=True,
            modo="archivo",
        )
        session.add(version)
        await session.flush()

        # Entry that matches student1
        e1 = EntradaPadron(
            tenant_id=data["tenant_id"],
            version_id=version.id,
            usuario_id=data["student1_id"],
            nombre="Student",
            apellidos="One",
            email_cifrado="encrypted1",
            email_hash="hash1",
            comision="A",
            regional="CABA",
        )
        session.add(e1)
        await session.flush()

        # Entry without user match
        e2 = EntradaPadron(
            tenant_id=data["tenant_id"],
            version_id=version.id,
            usuario_id=None,
            nombre="Student",
            apellidos="Three",
            email_cifrado="encrypted3",
            email_hash="hash3",
            comision="B",
        )
        session.add(e2)
        await session.flush()

        data["version_id"] = version.id
        data["entrada_ids"] = [e1.id, e2.id]

        # A previous inactive version (for versioning test)
        version_old = VersionPadron(
            tenant_id=data["tenant_id"],
            materia_id=data["materia_id"],
            cohorte_id=data["cohorte_id"],
            cargado_por=data["admin_id"],
            activa=False,
            modo="moodle_ws",
        )
        session.add(version_old)
        await session.flush()
        data["version_old_id"] = version_old.id

        await session.commit()

    await engine.dispose()
    return data


# ── Auth token fixtures ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def auth_token(seed_data: dict) -> str:
    """JWT for admin user (has padron:importar)."""
    return create_access_token(
        data={
            "sub": str(seed_data["admin_id"]),
            "tenant_id": str(seed_data["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def profesor_token(seed_data: dict) -> str:
    """JWT for PROFESOR user (has padron:importar, PROFESOR role)."""
    return create_access_token(
        data={
            "sub": str(seed_data["profesor_id"]),
            "tenant_id": str(seed_data["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def coordinador_token(seed_data: dict) -> str:
    """JWT for COORDINADOR user."""
    return create_access_token(
        data={
            "sub": str(seed_data["coordinador_id"]),
            "tenant_id": str(seed_data["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def no_perm_token(seed_data: dict) -> str:
    """JWT for user without padron:importar."""
    return create_access_token(
        data={
            "sub": str(seed_data["no_perm_user_id"]),
            "tenant_id": str(seed_data["tenant_id"]),
        }
    )


@pytest_asyncio.fixture
async def other_auth_token(seed_other_tenant: dict) -> str:
    """JWT for other tenant admin."""
    return create_access_token(
        data={
            "sub": str(seed_other_tenant["user_id"]),
            "tenant_id": str(seed_other_tenant["tenant_id"]),
        }
    )


# ── Helper: save MOODLE env vars ─────────────────────────────────────────
# Save original env so we can restore after tests


@pytest_asyncio.fixture(autouse=True)
async def _moodle_env():
    """Set up moodle env for tests that need it."""
    original_base = os.environ.get("MOODLE_BASE_URL")
    original_token = os.environ.get("MOODLE_TOKEN")
    os.environ["MOODLE_BASE_URL"] = "https://moodle.test.com"
    os.environ["MOODLE_TOKEN"] = "test-token-123"
    yield
    # Safe cleanup: use pop with default to avoid KeyError if test already removed
    if original_base is None:
        os.environ.pop("MOODLE_BASE_URL", None)
    else:
        os.environ["MOODLE_BASE_URL"] = original_base
    if original_token is None:
        os.environ.pop("MOODLE_TOKEN", None)
    else:
        os.environ["MOODLE_TOKEN"] = original_token


# ── Tests: moodle-sync ───────────────────────────────────────────────────


class TestMoodleSync:
    """POST /api/padron/moodle-sync — E1: sync from Moodle WS."""

    async def test_moodle_sync_success(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Sync from Moodle returns 201 with version data."""
        mock_alumnos = [
            {"nombre": "Juan", "apellidos": "Perez", "email": "jperez@test.com",
             "comision": "A", "regional": "CABA"},
            {"nombre": "Maria", "apellidos": "Lopez", "email": "mlopez@test.com",
             "comision": "A", "regional": None},
        ]

        with patch(
            "app.integrations.moodle_ws.MoodleClient"
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.sync_alumnos = AsyncMock(return_value=mock_alumnos)

            resp = await async_client.post(
                "/api/padron/moodle-sync",
                json={
                    "materia_id": str(seed_data["materia_id"]),
                    "cohorte_id": str(seed_data["cohorte_id"]),
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["total_entradas"] == 2
        assert body["modo"] == "moodle_ws"
        assert body["materia_id"] == str(seed_data["materia_id"])
        assert "version_id" in body

    async def test_moodle_sync_no_config(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """No moodle config returns 400."""
        # Temporarily unset env vars
        base_url = os.environ.pop("MOODLE_BASE_URL", None)
        token = os.environ.pop("MOODLE_TOKEN", None)

        resp = await async_client.post(
            "/api/padron/moodle-sync",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400
        assert "Moodle" in resp.json()["detail"]

        # Restore
        if base_url:
            os.environ["MOODLE_BASE_URL"] = base_url
        if token:
            os.environ["MOODLE_TOKEN"] = token

    async def test_moodle_sync_502_on_error(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Moodle connection error returns 502."""
        with patch(
            "app.integrations.moodle_ws.MoodleClient"
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.sync_alumnos = AsyncMock(
                side_effect=Exception("Connection refused")
            )

            resp = await async_client.post(
                "/api/padron/moodle-sync",
                json={
                    "materia_id": str(seed_data["materia_id"]),
                    "cohorte_id": str(seed_data["cohorte_id"]),
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        assert resp.status_code == 502

    async def test_moodle_sync_invalid_materia(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Non-existent materia returns 404."""
        resp = await async_client.post(
            "/api/padron/moodle-sync",
            json={
                "materia_id": str(uuid.uuid4()),
                "cohorte_id": str(uuid.uuid4()),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ── Tests: preview ───────────────────────────────────────────────────────


class TestPreview:
    """POST /api/padron/preview — E2: preview file import."""

    async def _upload(
        self, client, content: bytes, filename: str,
        materia_id: str, cohorte_id: str, token: str,
    ) -> object:
        """Helper to upload a file for preview."""
        return await client.post(
            "/api/padron/preview",
            files={"archivo": (filename, content)},
            params={"materia_id": materia_id, "cohorte_id": cohorte_id},
            headers={"Authorization": f"Bearer {token}"},
        )

    async def test_preview_csv_semicolon(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """CSV with semicolon separator parses correctly."""
        csv_content = (
            "nombre;apellidos;email;comision;regional\r\n"
            "Juan;Perez;jperez@test.com;A;CABA\r\n"
            "Maria;Lopez;mlopez@test.com;B;\r\n"
        ).encode("utf-8-sig")
        resp = await self._upload(
            async_client, csv_content, "padron.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filas"] == 2
        assert len(body["filas"]) == 2
        assert len(body["errores"]) == 0
        assert "comision" in body["columnas_detectadas"]

    async def test_preview_csv_comma(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """CSV with comma separator parses correctly."""
        csv_content = (
            "nombre,apellidos,email\r\n"
            "Juan,Perez,jperez@test.com\r\n"
        ).encode("utf-8-sig")
        resp = await self._upload(
            async_client, csv_content, "padron.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filas"] == 1

    async def test_preview_csv_with_errors(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """CSV with invalid rows returns errors per row."""
        csv_content = (
            "nombre;apellidos;email\r\n"
            "Juan;;jperez@test.com\r\n"
            ";;\r\n"
            "Maria;Lopez;mal-email\r\n"
        ).encode("utf-8-sig")
        resp = await self._upload(
            async_client, csv_content, "padron.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 200
        body = resp.json()
        # No valid rows since all have errors (row1 missing apellidos,
        # row2 empty/skipped, row3 invalid email)
        assert body["total_filas"] == 0
        assert len(body["errores"]) >= 2

    async def test_preview_unsupported_format(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Unsupported file format returns 400."""
        resp = await self._upload(
            async_client, b"some content", "data.pdf",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 400
        assert "soportado" in resp.json()["detail"].lower()

    async def test_preview_empty_file(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Empty file returns 400."""
        resp = await self._upload(
            async_client, b"", "padron.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 400


# ── Tests: import ────────────────────────────────────────────────────────


class TestImport:
    """POST /api/padron/import — E3: confirm file import."""

    async def test_import_success(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Import creates version and entries."""
        resp = await async_client.post(
            "/api/padron/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "filas": [
                    {"nombre": "Juan", "apellidos": "Perez",
                     "email": "juan@test.com"},
                    {"nombre": "Maria", "apellidos": "Lopez",
                     "email": "maria@test.com", "comision": "A"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["total_entradas"] == 2
        assert body["modo"] == "archivo"
        assert "version_id" in body

    async def test_import_with_user_match(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Students matching existing users get usuario_id assigned."""
        resp = await async_client.post(
            "/api/padron/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "filas": [
                    # student1@test.com matches seed student1
                    {"nombre": "Student", "apellidos": "One",
                     "email": "student1@test.com"},
                    # no match
                    {"nombre": "New", "apellidos": "User",
                     "email": "newuser@other.com"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["total_entradas"] == 2
        assert body["total_sin_usuario"] == 1  # one didn't match

    async def test_import_previous_version_deactivated(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Previous active version is deactivated on new import."""
        # First import
        resp1 = await async_client.post(
            "/api/padron/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "filas": [
                    {"nombre": "A", "apellidos": "B", "email": "a@test.com"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp1.status_code == 201
        first_vid = resp1.json()["version_id"]

        # Second import
        resp2 = await async_client.post(
            "/api/padron/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "filas": [
                    {"nombre": "C", "apellidos": "D", "email": "c@test.com"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp2.status_code == 201
        second_vid = resp2.json()["version_id"]

        # First version should no longer be active
        resp_detail = await async_client.get(
            f"/api/padron/versiones/{first_vid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp_detail.json()["activa"] is False

        # Second version should be active
        resp_detail2 = await async_client.get(
            f"/api/padron/versiones/{second_vid}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp_detail2.json()["activa"] is True

    async def test_import_empty_filas(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict
    ):
        """Empty filas list returns 400."""
        resp = await async_client.post(
            "/api/padron/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "filas": [],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400

    async def test_import_invalid_materia(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Non-existent materia returns 404."""
        resp = await async_client.post(
            "/api/padron/import",
            json={
                "materia_id": str(uuid.uuid4()),
                "cohorte_id": str(uuid.uuid4()),
                "filas": [
                    {"nombre": "A", "apellidos": "B", "email": "a@test.com"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ── Tests: vaciar ────────────────────────────────────────────────────────


class TestVaciar:
    """DELETE /api/padron/materia/{materia_id} — E4: vaciar materia."""

    async def test_vaciar_as_admin(
        self, async_client: AsyncClient, auth_token: str,
        seed_padron_version: dict,
    ):
        """Admin can vaciar all versions of a materia."""
        materia_id = seed_padron_version["materia_id"]
        resp = await async_client.delete(
            f"/api/padron/materia/{materia_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["versiones_desactivadas"] >= 1
        assert body["entradas_eliminadas"] >= 1
        assert body["materia_id"] == str(materia_id)

    async def test_vaciar_profesor_scope(
        self, async_client: AsyncClient, profesor_token: str,
        seed_padron_version: dict,
    ):
        """PROFESOR only vacia their own versions (none = empty)."""
        materia_id = seed_padron_version["materia_id"]
        # The profesor did not create any versions, so this should delete 0
        resp = await async_client.delete(
            f"/api/padron/materia/{materia_id}",
            headers={"Authorization": f"Bearer {profesor_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["versiones_desactivadas"] == 0

    async def test_vaciar_invalid_materia(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Vaciar non-existent materia returns 200 with 0 affected."""
        resp = await async_client.delete(
            f"/api/padron/materia/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["versiones_desactivadas"] == 0


# ── Tests: list versiones ────────────────────────────────────────────────


class TestListVersiones:
    """GET /api/padron/versiones — E5: list versions."""

    async def test_list_empty(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Empty list returns 200 with empty items."""
        resp = await async_client.get(
            "/api/padron/versiones",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_list_with_data(
        self, async_client: AsyncClient, auth_token: str,
        seed_padron_version: dict,
    ):
        """List returns created versions."""
        resp = await async_client.get(
            "/api/padron/versiones",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2  # version + version_old
        assert len(body["items"]) >= 2

    async def test_list_filter_by_materia(
        self, async_client: AsyncClient, auth_token: str,
        seed_padron_version: dict,
    ):
        """Filter by materia_id returns only matching."""
        resp = await async_client.get(
            f"/api/padron/versiones?materia_id={seed_padron_version['materia_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["materia_id"] == str(seed_padron_version["materia_id"])

    async def test_list_pagination(
        self, async_client: AsyncClient, auth_token: str,
        seed_padron_version: dict,
    ):
        """Pagination limits correctly."""
        resp = await async_client.get(
            "/api/padron/versiones?skip=0&limit=1",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) <= 1


# ── Tests: version detail ────────────────────────────────────────────────


class TestVersionDetail:
    """GET /api/padron/versiones/{version_id} — E6: version detail."""

    async def test_detail_success(
        self, async_client: AsyncClient, auth_token: str,
        seed_padron_version: dict,
    ):
        """Detail returns version with entries."""
        resp = await async_client.get(
            f"/api/padron/versiones/{seed_padron_version['version_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(seed_padron_version["version_id"])
        assert body["activa"] is True
        assert body["modo"] == "archivo"
        assert len(body["entradas"]) == 2
        assert body["total_entradas"] == 2

    async def test_detail_email_not_exposed(
        self, async_client: AsyncClient, auth_token: str,
        seed_padron_version: dict,
    ):
        """Email field is NOT returned, only email_hash."""
        resp = await async_client.get(
            f"/api/padron/versiones/{seed_padron_version['version_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        body = resp.json()
        for entry in body["entradas"]:
            assert "email" not in entry
            assert "email_hash" in entry
            assert "tiene_usuario" in entry

    async def test_detail_not_found(
        self, async_client: AsyncClient, auth_token: str
    ):
        """Non-existent version returns 404."""
        resp = await async_client.get(
            f"/api/padron/versiones/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ── Tests: permissions ───────────────────────────────────────────────────


class TestPermisos:
    """Auth guards for padron endpoints."""

    async def test_no_auth_returns_403(
        self, async_client: AsyncClient
    ):
        """All endpoints without token return 403."""
        endpoints = [
            ("POST", "/api/padron/moodle-sync"),
            ("POST", "/api/padron/preview"),
            ("POST", "/api/padron/import"),
            ("DELETE", f"/api/padron/materia/{uuid.uuid4()}"),
            ("GET", "/api/padron/versiones"),
            ("GET", f"/api/padron/versiones/{uuid.uuid4()}"),
        ]
        for method, url in endpoints:
            resp = await async_client.request(method, url)
            assert resp.status_code == 403, f"{method} {url} should be 403"

    async def test_without_permission_returns_403(
        self, async_client: AsyncClient, no_perm_token: str, seed_data: dict
    ):
        """User without padron:importar gets 403."""
        resp = await async_client.post(
            "/api/padron/moodle-sync",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {no_perm_token}"},
        )
        assert resp.status_code == 403


# ── Tests: multi-tenant ──────────────────────────────────────────────────


class TestMultiTenant:
    """Multi-tenant isolation tests."""

    async def test_tenant_b_sees_no_data(
        self, async_client: AsyncClient, other_auth_token: str,
        seed_padron_version: dict,
    ):
        """Tenant B does not see tenant A's versions."""
        resp = await async_client.get(
            "/api/padron/versiones",
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0

    async def test_tenant_b_cannot_access_version(
        self, async_client: AsyncClient, other_auth_token: str,
        seed_padron_version: dict,
    ):
        """Tenant B gets 404 on tenant A's version."""
        resp = await async_client.get(
            f"/api/padron/versiones/{seed_padron_version['version_id']}",
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 404
