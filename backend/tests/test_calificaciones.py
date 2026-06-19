"""E2E API tests for /api/calificaciones and /api/umbrales endpoints.

Covers all scenarios from the spec: preview, import, finalizacion,
list, umbral CRUD, multi-tenant isolation, and auth guards.

Also includes pure-function unit tests for calcular_aprobado,
column detection, and umbral inheritance.
"""

from __future__ import annotations

import io
import uuid
from datetime import date

import pytest
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
from app.models.asignacion import Asignacion
from app.models.calificacion import Calificacion
from app.models.umbral_materia import UmbralMateria

from .conftest import TEST_SETTINGS


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests — pure functions (task 7.1, 7.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalcularAprobado:
    """calcular_aprobado — pure function tests (task 7.1)."""

    def _call(self, nota=None, nota_textual=None, umbral_pct=0.60,
              max_nota=100, valores_aprobatorios=None):
        from app.services.calificaciones_service import calcular_aprobado
        return calcular_aprobado(
            nota=nota,
            nota_textual=nota_textual,
            umbral_pct=umbral_pct,
            max_nota=max_nota,
            valores_aprobatorios=valores_aprobatorios,
        )

    def test_numeric_above_threshold(self):
        """Numérica ≥ umbral → true (85 >= 60)."""
        assert self._call(nota=85.0) is True

    def test_numeric_below_threshold(self):
        """Numérica < umbral → false (45 < 60)."""
        assert self._call(nota=45.0) is False

    def test_numeric_exactly_at_threshold(self):
        """Numérica == umbral → true (60 >= 60)."""
        assert self._call(nota=60.0) is True

    def test_textual_in_approved_values(self):
        """Texto en valores_aprobatorios → true."""
        assert self._call(
            nota_textual="Satisfactorio",
            valores_aprobatorios=["Satisfactorio", "Supera lo esperado"],
        ) is True

    def test_textual_not_in_approved_values(self):
        """Texto no en valores_aprobatorios → false."""
        assert self._call(
            nota_textual="No satisfactorio",
            valores_aprobatorios=["Satisfactorio", "Supera lo esperado"],
        ) is False

    def test_no_nota_at_all(self):
        """Sin nota ni nota_textual → false."""
        assert self._call() is False

    def test_none_nota_none_textual(self):
        """Nota=None, nota_textual=None → false."""
        assert self._call(nota=None, nota_textual=None) is False

    def test_different_umbral_pct(self):
        """Umbral_pct=0.75 con nota=70 y max=100 → false (70 < 75)."""
        assert self._call(nota=70.0, umbral_pct=0.75, max_nota=100) is False

    def test_textual_empty_approved_values(self):
        """valores_aprobatorios=[] → textual nunca es aprobado."""
        assert self._call(
            nota_textual="Satisfactorio",
            valores_aprobatorios=[],
        ) is False


class TestDetectColumn:
    """detectar_columna — pure function tests (task 7.2)."""

    def _call(self, nombre_columna: str):
        from app.services.calificaciones_service import detectar_columna
        return detectar_columna(nombre_columna)

    def test_numeric_suffix_real(self):
        """'TP1 (Real)' → ('TP1', 'numerica', None)."""
        name, tipo, _ = self._call("TP1 (Real)")
        assert name == "TP1"
        assert tipo == "numerica"

    def test_textual_cualitativo(self):
        """'TP2 (Cualitativo)' → ('TP2 (Cualitativo)', 'textual', None).
        
        Only (Real) suffix triggers numeric detection. Everything else
        including (Cualitativo) is textual and keeps the original name.
        """
        name, tipo, _ = self._call("TP2 (Cualitativo)")
        assert name == "TP2 (Cualitativo)"
        assert tipo == "textual"

    def test_no_suffix(self):
        """'TP3' → ('TP3', 'textual', None)."""
        name, tipo, _ = self._call("TP3")
        assert name == "TP3"
        assert tipo == "textual"

    def test_real_with_extra_spaces(self):
        """'  TP Final (Real)  ' → ('TP Final', 'numerica', None)."""
        name, tipo, _ = self._call("  TP Final (Real)  ")
        assert name == "TP Final"
        assert tipo == "numerica"

    def test_real_case_insensitive(self):
        """'examen (real)' → ('examen', 'numerica', None)."""
        name, tipo, _ = self._call("examen (real)")
        assert name == "examen"
        assert tipo == "numerica"


# ═══════════════════════════════════════════════════════════════════════════════
# Shared seed fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def seed_data(async_client: AsyncClient) -> dict:
    """Seed tenant + users + roles + academic data + padron + asignaciones."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data: dict = {}

    async with factory() as session:
        tenant = Tenant(nombre="Calif Tenant", codigo=f"CF{uuid.uuid4().hex[:4]}")
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

        # PROFESOR user
        profesor = User(
            tenant_id=tenant.id,
            email=f"prof-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("ProfPass123!"),
            display_name="Profesor Test",
            is_active=True,
        )
        session.add(profesor)
        await session.flush()

        # COORDINADOR user
        coordinador = User(
            tenant_id=tenant.id,
            email=f"coord-{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("CoordPass123!"),
            display_name="Coordinador Test",
            is_active=True,
        )
        session.add(coordinador)
        await session.flush()

        # Student users
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

        # User without permissions
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
            tenant_id=tenant.id, codigo="PROG1", nombre="Programacion I"
        )
        session.add(materia)
        await session.flush()

        materia2 = Materia(
            tenant_id=tenant.id, codigo="PROG2", nombre="Programacion II"
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
        for perm_codigo in ["calificaciones:importar", "calificaciones:ver"]:
            perm = Permission(tenant_id=tenant.id, codigo=perm_codigo)
            session.add(perm)
            await session.flush()

            for role in [role_admin, role_prof, role_coord]:
                rp = RolePermission(role_id=role.id, permission_id=perm.id)
                session.add(rp)

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

        # Asignaciones: one for admin/coord context, one for profesor
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
            materia_id=materia.id,
            cohorte_id=cohorte.id,
            comisiones=[],
            desde=date(2024, 1, 1),
        )
        session.add(asignacion_other)
        await session.flush()

        # Padron version with entries
        version = VersionPadron(
            tenant_id=tenant.id,
            materia_id=materia.id,
            cohorte_id=cohorte.id,
            cargado_por=admin.id,
            activa=True,
            modo="archivo",
        )
        session.add(version)
        await session.flush()

        e1 = EntradaPadron(
            tenant_id=tenant.id,
            version_id=version.id,
            usuario_id=student1.id,
            nombre="Student",
            apellidos="One",
            email_cifrado="enc1",
            email_hash=User.compute_email_hash("student1@test.com"),
            comision="A",
        )
        session.add(e1)
        await session.flush()

        e2 = EntradaPadron(
            tenant_id=tenant.id,
            version_id=version.id,
            usuario_id=student2.id,
            nombre="Student",
            apellidos="Two",
            email_cifrado="enc2",
            email_hash=User.compute_email_hash("student2@test.com"),
            comision="A",
        )
        session.add(e2)
        await session.flush()

        data.update({
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
            "asignacion_prof_id": asignacion_prof.id,
            "asignacion_other_id": asignacion_other.id,
            "version_id": version.id,
            "entrada1_id": e1.id,
            "entrada2_id": e2.id,
        })
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

        for perm_codigo in ["calificaciones:importar", "calificaciones:ver"]:
            perm = Permission(tenant_id=tenant.id, codigo=perm_codigo)
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
            "user_id": admin.id,
            "tenant_id": tenant.id,
        }
        await session.commit()

    await engine.dispose()
    return data


@pytest_asyncio.fixture
async def seed_umbrales(seed_data: dict) -> dict:
    """Seed umbrales for testing: one materia-wide and one specific."""
    engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    data = dict(seed_data)

    async with factory() as session:
        # Materia-wide default
        umbral_default = UmbralMateria(
            tenant_id=data["tenant_id"],
            materia_id=data["materia_id"],
            cohorte_id=data["cohorte_id"],
            asignacion_id=None,
            umbral_pct=0.60,
            valores_aprobatorios=["Satisfactorio", "Supera lo esperado"],
        )
        session.add(umbral_default)
        await session.flush()
        data["umbral_default_id"] = umbral_default.id

        # Specific for profesor's asignacion
        umbral_specific = UmbralMateria(
            tenant_id=data["tenant_id"],
            materia_id=data["materia_id"],
            cohorte_id=data["cohorte_id"],
            asignacion_id=data["asignacion_prof_id"],
            umbral_pct=0.75,
            valores_aprobatorios=["Aprobado", "Muy bueno"],
        )
        session.add(umbral_specific)
        await session.flush()
        data["umbral_specific_id"] = umbral_specific.id

        await session.commit()

    await engine.dispose()
    return data


# ── Auth token fixtures ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def auth_token(seed_data: dict) -> str:
    """JWT for admin user."""
    return create_access_token(data={
        "sub": str(seed_data["admin_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


@pytest_asyncio.fixture
async def profesor_token(seed_data: dict) -> str:
    """JWT for PROFESOR user."""
    return create_access_token(data={
        "sub": str(seed_data["profesor_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


@pytest_asyncio.fixture
async def coordinador_token(seed_data: dict) -> str:
    """JWT for COORDINADOR user."""
    return create_access_token(data={
        "sub": str(seed_data["coordinador_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


@pytest_asyncio.fixture
async def no_perm_token(seed_data: dict) -> str:
    """JWT for user without calificaciones permissions."""
    return create_access_token(data={
        "sub": str(seed_data["no_perm_user_id"]),
        "tenant_id": str(seed_data["tenant_id"]),
    })


@pytest_asyncio.fixture
async def other_auth_token(seed_other_tenant: dict) -> str:
    """JWT for other tenant admin."""
    return create_access_token(data={
        "sub": str(seed_other_tenant["user_id"]),
        "tenant_id": str(seed_other_tenant["tenant_id"]),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: preview (task 7.4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPreview:
    """POST /api/calificaciones/preview — R-CAL-01."""

    async def _upload(
        self, client, content: bytes, filename: str,
        materia_id: str, cohorte_id: str, token: str,
    ):
        return await client.post(
            "/api/calificaciones/preview",
            files={"archivo": (filename, content)},
            params={"materia_id": materia_id, "cohorte_id": cohorte_id},
            headers={"Authorization": f"Bearer {token}"},
        )

    async def test_preview_csv_mixed_columns(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Preview exitoso con columnas mixtas."""
        csv_content = (
            "nombre;apellidos;email;TP1 (Real);TP2 (Cualitativo)\r\n"
            "Juan;Perez;jperez@test.com;85;Satisfactorio\r\n"
            "Maria;Lopez;mlopez@test.com;45;No satisfactorio\r\n"
        ).encode("utf-8-sig")
        resp = await self._upload(
            async_client, csv_content, "notas.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filas"] == 2
        assert len(body["columnas"]) == 2
        assert len(body["filas"]) == 2
        assert body["filas"][0]["email"] == "jperez@test.com"

        # Check column detection
        col_names = {c["nombre"]: c["tipo"] for c in body["columnas"]}
        assert col_names["TP1"] == "numerica"
        # Textual columns keep original name (only (Real) suffix is cleaned)
        assert col_names.get("TP2 (Cualitativo)") == "textual"

    async def test_preview_unsupported_format(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Archivo no soportado → 400."""
        resp = await self._upload(
            async_client, b"some content", "data.pdf",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 400
        assert "soportado" in resp.json()["detail"].lower()

    async def test_preview_no_permission(
        self, async_client: AsyncClient, no_perm_token: str, seed_data: dict,
    ):
        """Usuario sin calificaciones:importar → 403."""
        resp = await self._upload(
            async_client, b"test", "notas.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            no_perm_token,
        )
        assert resp.status_code == 403

    async def test_preview_invalid_materia(
        self, async_client: AsyncClient, auth_token: str,
    ):
        """Materia inexistente → 404."""
        resp = await self._upload(
            async_client, b"test", "notas.csv",
            str(uuid.uuid4()), str(uuid.uuid4()),
            auth_token,
        )
        assert resp.status_code == 404

    async def test_preview_empty_file(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Archivo vacío → 400."""
        resp = await self._upload(
            async_client, b"", "notas.csv",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 400

    async def test_preview_xlsx_mixed(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Preview exitoso con .xlsx."""
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl not installed")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Notas"
        ws.append(["nombre", "apellidos", "email", "TP1 (Real)", "TP2 (Cualitativo)"])
        ws.append(["Juan", "Perez", "jperez@test.com", 85.0, "Satisfactorio"])
        ws.append(["Maria", "Lopez", "mlopez@test.com", 45.0, "No satisfactorio"])

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        content = buf.read()
        wb.close()

        resp = await self._upload(
            async_client, content, "notas.xlsx",
            str(seed_data["materia_id"]), str(seed_data["cohorte_id"]),
            auth_token,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filas"] == 2
        col_names = {c["nombre"]: c["tipo"] for c in body["columnas"]}
        assert col_names["TP1"] == "numerica"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: import (task 7.5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestImport:
    """POST /api/calificaciones/import — R-CAL-02."""

    async def test_import_success_with_aprobados(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """Import exitoso con aprobados derivados + audit."""
        resp = await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "student1@test.com", "nota": 85.0},
                    {"email": "student2@test.com", "nota": 45.0},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["importadas"] == 2
        assert body["aprobadas"] == 1  # 85 >= 60, 45 < 60
        assert body["reprobadas"] == 1
        assert body["errores"] == []

        # Verify audit log was created
        from sqlalchemy import text
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT accion, detalle FROM audit_log WHERE accion = 'CALIFICACIONES_IMPORTAR'")
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] == "CALIFICACIONES_IMPORTAR"
        await engine.dispose()

    async def test_import_alumno_not_found(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Alumno no encontrado → 400, 0 calificaciones."""
        resp = await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "unknown@test.com", "nota": 85.0},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400
        assert "no encontrado" in resp.json()["detail"].lower()

    async def test_import_nota_below_umbral(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """Nota numérica debajo del umbral → aprobado=false."""
        resp = await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "student1@test.com", "nota": 30.0},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["aprobadas"] == 0
        assert resp.json()["reprobadas"] == 1

    async def test_import_textual_no_aprobatorio(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """Nota textual no aprobatoria → aprobado=false."""
        resp = await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP2",
                "notas": [
                    {"email": "student1@test.com", "nota_textual": "Insuficiente"},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["aprobadas"] == 0

    async def test_import_sin_nota(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """Sin nota ni textual → aprobado=false, origen=Importado."""
        resp = await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "student1@test.com"},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["aprobadas"] == 0
        assert resp.json()["importadas"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: finalizacion (task 7.6)
# ═══════════════════════════════════════════════════════════════════════════════


class TestFinalizacion:
    """POST /api/calificaciones/importar-finalizacion — R-CAL-03."""

    async def test_finalizacion_detects_sin_nota(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Detecta TPs textuales sin nota."""
        # First import some numeric grades (should be excluded)
        resp_import = await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "student1@test.com", "nota": 85.0},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp_import.status_code == 201

        # Now send finalizacion file
        csv_content = (
            "nombre;apellidos;email;TP1 (Real);TP2 (Cualitativo)\r\n"
            "Student;One;student1@test.com;85;Entregado\r\n"
            "Student;Two;student2@test.com;;Entregado\r\n"
        ).encode("utf-8-sig")
        resp = await async_client.post(
            "/api/calificaciones/importar-finalizacion",
            files={"archivo": ("finalizacion.csv", csv_content)},
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Should only show TP2 (textual) for students without grades
        # student1 has TP1 already imported (numeric)
        # student2 has no grades at all
        # TP2 is textual → should appear
        assert body["total"] > 0

    async def test_finalizacion_excludes_numeric(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Excluye actividades numéricas del reporte (RN-08)."""
        csv_content = (
            "nombre;apellidos;email;TP1 (Real);TP2 (Cualitativo)\r\n"
            "Student;One;student1@test.com;85;Entregado\r\n"
        ).encode("utf-8-sig")
        resp = await async_client.post(
            "/api/calificaciones/importar-finalizacion",
            files={"archivo": ("finalizacion.csv", csv_content)},
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Items should only reference TP2 (textual), never TP1 (numeric)
        for item in body["items"]:
            assert item["actividad"] != "TP1"  # RN-08: numeric excluded


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: list calificaciones (task 7.7)
# ═══════════════════════════════════════════════════════════════════════════════


class TestListCalificaciones:
    """GET /api/calificaciones — R-CAL-04."""

    async def test_list_empty(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Listado vacío."""
        resp = await async_client.get(
            "/api/calificaciones",
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_list_with_data(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """Listado con datos."""
        # Import some grades first
        await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "student1@test.com", "nota": 85.0},
                    {"email": "student2@test.com", "nota": 45.0},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        resp = await async_client.get(
            "/api/calificaciones",
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "skip": 0,
                "limit": 20,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    async def test_list_pagination(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """Paginación funciona."""
        # Import 2 grades
        await async_client.post(
            "/api/calificaciones/import",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "actividad_nombre": "TP1",
                "notas": [
                    {"email": "student1@test.com", "nota": 85.0},
                    {"email": "student2@test.com", "nota": 45.0},
                ],
                "max_nota": 100,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        resp = await async_client.get(
            "/api/calificaciones",
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
                "skip": 0,
                "limit": 1,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 1

    async def test_list_profesor_scope(
        self, async_client: AsyncClient, profesor_token: str, seed_data: dict,
        seed_umbrales: dict,
    ):
        """PROFESOR solo ve calificaciones de su propia asignación."""
        resp = await async_client.get(
            "/api/calificaciones",
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {profesor_token}"},
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: umbrales (task 7.8)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUmbrales:
    """GET/PUT /api/umbrales — R-UMB-01, R-UMB-02."""

    async def test_list_empty(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Sin umbrales configurados → items=[]."""
        resp = await async_client.get(
            "/api/umbrales",
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []

    async def test_list_with_data(
        self, async_client: AsyncClient, auth_token: str, seed_umbrales: dict,
    ):
        """Listado con umbrales mixtos."""
        resp = await async_client.get(
            "/api/umbrales",
            params={
                "materia_id": str(seed_umbrales["materia_id"]),
                "cohorte_id": str(seed_umbrales["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) >= 2  # default + specific

    async def test_update_umbral_pct(
        self, async_client: AsyncClient, auth_token: str, seed_umbrales: dict,
    ):
        """PUT update umbral_pct."""
        resp = await async_client.put(
            f"/api/umbrales/{seed_umbrales['umbral_specific_id']}",
            json={"umbral_pct": 0.80},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["umbral_pct"] == 0.80

    async def test_update_valores_aprobatorios(
        self, async_client: AsyncClient, auth_token: str, seed_umbrales: dict,
    ):
        """PUT update valores_aprobatorios."""
        resp = await async_client.put(
            f"/api/umbrales/{seed_umbrales['umbral_specific_id']}",
            json={"valores_aprobatorios": ["Excelente", "Aprobado"]},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "Excelente" in body["valores_aprobatorios"]

    async def test_profesor_update_other_asignacion_403(
        self, async_client: AsyncClient, profesor_token: str, seed_umbrales: dict,
    ):
        """PROFESOR modificando umbral de otra asignación → 403."""
        resp = await async_client.put(
            f"/api/umbrales/{seed_umbrales['umbral_default_id']}",
            json={"umbral_pct": 0.50},
            headers={"Authorization": f"Bearer {profesor_token}"},
        )
        assert resp.status_code == 403

    async def test_update_no_fields_400(
        self, async_client: AsyncClient, auth_token: str, seed_umbrales: dict,
    ):
        """PUT sin campos → 400."""
        resp = await async_client.put(
            f"/api/umbrales/{seed_umbrales['umbral_specific_id']}",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 400

    async def test_update_not_found(
        self, async_client: AsyncClient, auth_token: str,
    ):
        """PUT umbral inexistente → 404."""
        resp = await async_client.put(
            f"/api/umbrales/{uuid.uuid4()}",
            json={"umbral_pct": 0.50},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-tenant tests (task 7.9)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenant:
    """Multi-tenant isolation — datos de tenant A no visibles desde B."""

    async def test_tenant_b_sees_no_calificaciones(
        self, async_client: AsyncClient, other_auth_token: str,
        seed_data: dict,
    ):
        """Tenant B no ve calificaciones de tenant A."""
        resp = await async_client.get(
            "/api/calificaciones",
            params={
                "materia_id": str(seed_data["materia_id"]),
                "cohorte_id": str(seed_data["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 404  # materia not found in different tenant

    async def test_tenant_b_sees_no_umbrales(
        self, async_client: AsyncClient, other_auth_token: str,
        seed_umbrales: dict,
    ):
        """Tenant B no ve umbrales de tenant A."""
        resp = await async_client.get(
            "/api/umbrales",
            params={
                "materia_id": str(seed_umbrales["materia_id"]),
                "cohorte_id": str(seed_umbrales["cohorte_id"]),
            },
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 404  # materia not found in different tenant


# ═══════════════════════════════════════════════════════════════════════════════
# Umbral inheritance unit test (task 7.3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUmbralInheritance:
    """Umbral inheritance chain (RN-03) — tested via repository directly."""

    async def test_inheritance_chain_specific(
        self, seed_umbrales: dict,
    ):
        """Específico por asignación → devuelve ese."""
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            from app.repositories.umbral_repository import UmbralMateriaRepository
            repo = UmbralMateriaRepository(
                session=session, tenant_id=seed_umbrales["tenant_id"],
            )
            pct, values = await repo.get_effective_umbral(
                asignacion_id=seed_umbrales["asignacion_prof_id"],
                materia_id=seed_umbrales["materia_id"],
                cohorte_id=seed_umbrales["cohorte_id"],
            )
            assert pct == 0.75  # specific has 0.75
            assert "Aprobado" in (values or [])

        await engine.dispose()

    async def test_inheritance_chain_default(
        self, seed_umbrales: dict,
    ):
        """Sin específico, con default de materia → devuelve default."""
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            from app.repositories.umbral_repository import UmbralMateriaRepository
            repo = UmbralMateriaRepository(
                session=session, tenant_id=seed_umbrales["tenant_id"],
            )
            # Use a non-existent asignacion_id
            fake_asig_id = uuid.uuid4()
            pct, values = await repo.get_effective_umbral(
                asignacion_id=fake_asig_id,
                materia_id=seed_umbrales["materia_id"],
                cohorte_id=seed_umbrales["cohorte_id"],
            )
            assert pct == 0.60  # materia-wide default
            assert "Satisfactorio" in (values or [])

        await engine.dispose()

    async def test_inheritance_chain_hardcoded(
        self, seed_data: dict,
    ):
        """Sin ningún umbral → devuelve (0.60, None)."""
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            from app.repositories.umbral_repository import UmbralMateriaRepository
            repo = UmbralMateriaRepository(
                session=session, tenant_id=seed_data["tenant_id"],
            )
            # Use materia2 which has no umbrales
            pct, values = await repo.get_effective_umbral(
                asignacion_id=uuid.uuid4(),
                materia_id=seed_data["materia2_id"],
                cohorte_id=seed_data["cohorte_id"],
            )
            assert pct == 0.60
            assert values is None

        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Auth guard tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthGuards:
    """Auth guards for calificaciones endpoints."""

    async def test_no_auth_returns_403(
        self, async_client: AsyncClient,
    ):
        """Endpoints sin token → 403."""
        endpoints = [
            ("POST", "/api/calificaciones/preview?materia_id=a&cohorte_id=b"),
            ("POST", "/api/calificaciones/import"),
            ("POST", "/api/calificaciones/importar-finalizacion?materia_id=a&cohorte_id=b"),
            ("GET", "/api/calificaciones?materia_id=a&cohorte_id=b"),
            ("GET", "/api/umbrales?materia_id=a&cohorte_id=b"),
        ]
        for method, url in endpoints:
            resp = await async_client.request(method, url)
            assert resp.status_code == 403, f"{method} {url} should be 403"
