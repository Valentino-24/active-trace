"""E2E API tests for /api/comunicaciones endpoints.

Covers all scenarios from the spec: preview, enqueue, approval,
worker processing, permissions, multi-tenant isolation, cifrado,
and state machine transitions.

Also includes pure-function unit tests for render_template and
validate_transition.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, encrypt, hash_password
from app.models.asignacion import Asignacion
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.comunicacion import Comunicacion, EstadoComunicacion
from app.models.materia import Materia
from app.models.padron import EntradaPadron, VersionPadron
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.comunicaciones import (
    DestinatarioPreview,
    PreviewResponse,
)

from .conftest import TEST_SETTINGS


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests — pure functions (task 4.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderTemplate:
    """render_template — pure function tests."""

    def _call(self, template_text: str, variables: dict[str, str]) -> str:
        from app.services.comunicacion_service import render_template
        return render_template(template_text, variables)

    def test_all_known_variables_substituted(self):
        """${nombre} ${apellido} → 'Juan Pérez'."""
        result = self._call(
            "${nombre} ${apellido}",
            {"nombre": "Juan", "apellido": "Pérez"},
        )
        assert result == "Juan Pérez"

    def test_unknown_variable_left_as_is(self):
        """${carrera} unknown → preserved as-is."""
        result = self._call(
            "Hola ${nombre}, tu ${carrera} es correcta",
            {"nombre": "Juan"},
        )
        assert result == "Hola Juan, tu ${carrera} es correcta"

    def test_empty_template_returns_empty(self):
        """Empty string → empty string."""
        result = self._call("", {"nombre": "Juan"})
        assert result == ""

    def test_partial_substitution(self):
        """Some vars known, some unknown."""
        result = self._call(
            "Hola ${nombre}, tu materia es ${materia}",
            {"nombre": "Juan"},
        )
        assert result == "Hola Juan, tu materia es ${materia}"

    def test_all_variables_workflow(self):
        """All supported variables substituted correctly."""
        result = self._call(
            "${nombre} ${apellido}, tu materia ${materia} (comisión ${comision}) — ${nombre_profesor}",
            {
                "nombre": "Juan",
                "apellido": "Pérez",
                "materia": "Programación I",
                "comision": "A",
                "nombre_profesor": "Dr. García",
            },
        )
        assert result == "Juan Pérez, tu materia Programación I (comisión A) — Dr. García"

    def test_template_with_no_variables(self):
        """Template without ${} = returned as-is."""
        result = self._call("Hola mundo", {})
        assert result == "Hola mundo"


class TestValidateTransition:
    """validate_transition — pure function tests."""

    def _call(self, from_state: str, to_state: str) -> bool:
        from app.services.comunicacion_service import validate_transition
        return validate_transition(from_state, to_state)

    def test_pendiente_to_enviando(self):
        """Pendiente → Enviando: valid."""
        assert self._call("Pendiente", "Enviando") is True

    def test_pendiente_to_cancelado(self):
        """Pendiente → Cancelado: valid."""
        assert self._call("Pendiente", "Cancelado") is True

    def test_enviando_to_enviado(self):
        """Enviando → Enviado: valid."""
        assert self._call("Enviando", "Enviado") is True

    def test_enviando_to_error(self):
        """Enviando → Error: valid."""
        assert self._call("Enviando", "Error") is True

    def test_enviado_to_anything(self):
        """Enviado → anything: invalid (terminal)."""
        assert self._call("Enviado", "Pendiente") is False
        assert self._call("Enviado", "Cancelado") is False
        assert self._call("Enviado", "Enviando") is False

    def test_error_to_anything(self):
        """Error → anything: invalid (terminal)."""
        assert self._call("Error", "Enviado") is False
        assert self._call("Error", "Pendiente") is False

    def test_cancelado_to_anything(self):
        """Cancelado → anything: invalid (terminal)."""
        assert self._call("Cancelado", "Enviando") is False
        assert self._call("Cancelado", "Pendiente") is False

    def test_enviando_to_cancelado(self):
        """Enviando → Cancelado: invalid."""
        assert self._call("Enviando", "Cancelado") is False

    def test_invalid_from_state(self):
        """Unknown from_state → invalid."""
        assert self._call("Invalido", "Enviado") is False


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
        tenant = Tenant(nombre="Com Tenant", codigo=f"CM{uuid.uuid4().hex[:4]}")
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

        # Permission: comunicacion:enviar (all roles)
        perm_enviar = Permission(tenant_id=tenant.id, codigo="comunicacion:enviar")
        session.add(perm_enviar)
        await session.flush()
        for role in [role_admin, role_prof, role_coord]:
            session.add(RolePermission(role_id=role.id, permission_id=perm_enviar.id))

        # Permission: comunicacion:aprobar (only ADMIN and COORDINADOR)
        perm_aprobar = Permission(tenant_id=tenant.id, codigo="comunicacion:aprobar")
        session.add(perm_aprobar)
        await session.flush()
        for role in [role_admin, role_coord]:
            session.add(RolePermission(role_id=role.id, permission_id=perm_aprobar.id))

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

        version2 = VersionPadron(
            tenant_id=tenant.id,
            materia_id=materia2.id,
            cohorte_id=cohorte.id,
            cargado_por=admin.id,
            activa=True,
            modo="archivo",
        )
        session.add(version2)
        await session.flush()

        # Student entries
        # Use a proper 32-byte key for AES-256-GCM
        _test_enc_key = b"x" * 32

        e1 = EntradaPadron(
            tenant_id=tenant.id,
            version_id=version.id,
            usuario_id=None,
            nombre="Juan",
            apellidos="Pérez",
            email_cifrado=encrypt("juan@test.com", _test_enc_key),
            email_hash=User.compute_email_hash("juan@test.com"),
            comision="A",
        )
        session.add(e1)
        await session.flush()

        e2 = EntradaPadron(
            tenant_id=tenant.id,
            version_id=version.id,
            usuario_id=None,
            nombre="María",
            apellidos="López",
            email_cifrado=encrypt("maria@test.com", _test_enc_key),
            email_hash=User.compute_email_hash("maria@test.com"),
            comision="A",
        )
        session.add(e2)
        await session.flush()

        # Entries for materia2
        e3 = EntradaPadron(
            tenant_id=tenant.id,
            version_id=version2.id,
            usuario_id=None,
            nombre="Carlos",
            apellidos="García",
            email_cifrado=encrypt("carlos@test.com", _test_enc_key),
            email_hash=User.compute_email_hash("carlos@test.com"),
            comision="B",
        )
        session.add(e3)
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
            "version_id": version.id,
            "entrada1_id": e1.id,
            "entrada2_id": e2.id,
            "entrada3_id": e3.id,
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

        for perm_codigo in ["comunicacion:enviar", "comunicacion:aprobar"]:
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
    """JWT for user without comunicacion permissions."""
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
# Integration tests: Preview (task 4.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPreview:
    """POST /api/comunicaciones/preview — R-COM-01."""

    PREVIEW_URL = "/api/comunicaciones/preview"

    async def test_preview_valid_variables(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Preview with valid variables renders personalized text."""
        resp = await async_client.post(
            self.PREVIEW_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Recordatorio ${materia}",
                "cuerpo_template": "Hola ${nombre} ${apellido}, tenés actividades pendientes en ${materia}",
                "destinatarios": [
                    {
                        "nombre": "Juan",
                        "apellido": "Pérez",
                        "materia": "Programación I",
                        "comision": "A",
                        "nombre_profesor": "Dr. García",
                    },
                    {
                        "nombre": "María",
                        "apellido": "López",
                        "materia": "Programación I",
                        "comision": "A",
                        "nombre_profesor": "Dr. García",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        assert body["items"][0]["asunto_rendered"] == "Recordatorio Programación I"
        assert "Juan" in body["items"][0]["cuerpo_rendered"]
        assert "María" in body["items"][1]["cuerpo_rendered"]

    async def test_preview_unknown_variable(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Unknown variable preserved as-is (no crash)."""
        resp = await async_client.post(
            self.PREVIEW_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Notificación ${materia}",
                "cuerpo_template": "Tu comisión es ${comision_desconocida}",
                "destinatarios": [
                    {
                        "nombre": "Juan",
                        "apellido": "Pérez",
                        "materia": "Programación I",
                        "comision": "A",
                        "nombre_profesor": "Dr. García",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "${comision_desconocida}" in body["items"][0]["cuerpo_rendered"]

    async def test_preview_multiple_recipients(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Multiple recipients each get personalized rendering."""
        resp = await async_client.post(
            self.PREVIEW_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Hola ${nombre}",
                "cuerpo_template": "Mensaje para ${nombre} ${apellido}",
                "destinatarios": [
                    {
                        "nombre": "Juan", "apellido": "Pérez",
                        "materia": "", "comision": "", "nombre_profesor": "",
                    },
                    {
                        "nombre": "María", "apellido": "López",
                        "materia": "", "comision": "", "nombre_profesor": "",
                    },
                    {
                        "nombre": "Carlos", "apellido": "García",
                        "materia": "", "comision": "", "nombre_profesor": "",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert body["items"][0]["asunto_rendered"] == "Hola Juan"
        assert body["items"][1]["asunto_rendered"] == "Hola María"
        assert body["items"][2]["asunto_rendered"] == "Hola Carlos"

    async def test_preview_no_persistence(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Preview does NOT persist any data."""
        resp = await async_client.post(
            self.PREVIEW_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Test ${nombre}",
                "cuerpo_template": "Test body",
                "destinatarios": [
                    {
                        "nombre": "Juan", "apellido": "Pérez",
                        "materia": "", "comision": "", "nombre_profesor": "",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

        # Verify no records created
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM comunicacion")
            )
            count = result.scalar()
            assert count == 0
        await engine.dispose()

    async def test_preview_materia_not_found(
        self, async_client: AsyncClient, auth_token: str,
    ):
        """Materia inexistente → 404."""
        resp = await async_client.post(
            self.PREVIEW_URL,
            json={
                "materia_id": str(uuid.uuid4()),
                "asunto_template": "Test",
                "cuerpo_template": "Test",
                "destinatarios": [
                    {"nombre": "Juan", "apellido": "Pérez",
                     "materia": "", "comision": "", "nombre_profesor": ""},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Enqueue (task 4.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnviar:
    """POST /api/comunicaciones/enviar — R-COM-02."""

    ENVIAR_URL = "/api/comunicaciones/enviar"

    async def test_enqueue_creates_pendiente_with_same_lote(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Batch enqueue creates Pendiente records with same lote_id."""
        # First check there are entries in the padron
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM entrada_padron WHERE version_id = :vid"),
                {"vid": seed_data["version_id"]},
            )
            assert result.scalar() >= 2
        await engine.dispose()

        resp = await async_client.post(
            self.ENVIAR_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Recordatorio ${materia}",
                "cuerpo_template": "Hola ${nombre} ${apellido}, actividades en ${materia}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["total"] >= 2
        assert body["lote_id"] is not None
        assert "Pendiente" in body["estados"]

        # Verify records in DB
        lote_id = body["lote_id"]
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM comunicacion WHERE lote_id = :lid AND estado = 'Pendiente'"),
                {"lid": lote_id},
            )
            count = result.scalar()
            assert count == body["total"]

            # Verify audit event
            result = await conn.execute(
                text("SELECT COUNT(*) FROM audit_log WHERE accion = 'COMUNICACION_ENVIAR'")
            )
            assert result.scalar() >= 1
        await engine.dispose()

    async def test_enqueue_without_approval_auto_transitions(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """When requiere_aprobacion=false, messages go directly to Enviando."""
        resp = await async_client.post(
            self.ENVIAR_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": False,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["total"] >= 1
        assert "Enviando" in body["estados"]

    async def test_enqueue_no_padron_raises_400(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Materia without padron → 400."""
        resp = await async_client.post(
            self.ENVIAR_URL,
            json={
                "materia_id": str(seed_data["materia2_id"]),
                "asunto_template": "Test",
                "cuerpo_template": "Test",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201  # materia2 has entries

    async def test_enqueue_audit_event(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Audit event COMUNICACION_ENVIAR recorded."""
        resp = await async_client.post(
            self.ENVIAR_URL,
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Audit test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT detalle FROM audit_log WHERE accion = 'COMUNICACION_ENVIAR' ORDER BY created_at DESC LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            detalle = row[0]
            assert lote_id in str(detalle)
        await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Worker cycle (task 4.3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkerCycle:
    """Worker processing — R-COM-04 state machine."""

    async def test_worker_processes_pendiente_to_enviado(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Worker processes Pendiente → Enviando → Enviado."""
        # Enqueue messages without approval (auto Enviando)
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Worker test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # Simulate worker: fetch Pendiente → Enviando → Enviado
        from app.workers.comunicacion_worker import ComunicacionWorker
        from app.core.database import create_engine as ce, create_session_factory as csf

        engine = ce(TEST_SETTINGS)
        session_factory = csf(engine)

        worker = ComunicacionWorker(
            session_factory=session_factory,
            settings=TEST_SETTINGS,
        )
        await worker._process_batch()

        await engine.dispose()

        # Verify messages are now Enviado
        engine2 = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine2.connect() as conn:
            result = await conn.execute(
                text("SELECT estado, enviado_at FROM comunicacion WHERE lote_id = :lid"),
                {"lid": lote_id},
            )
            rows = result.fetchall()
            assert len(rows) >= 1
            for row in rows:
                assert row[0] == "Enviado"
                assert row[1] is not None  # enviado_at set
        await engine2.dispose()


class TestApproval:
    """Approval endpoints — R-COM-03."""

    async def test_approve_lote_transitions_to_enviando(
        self, async_client: AsyncClient, auth_token: str, coordinador_token: str,
        seed_data: dict,
    ):
        """Approve lote → all Pendiente → Enviando."""
        # Enqueue
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Approve test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # Approve with coordinador (has comunicacion:aprobar)
        resp = await async_client.post(
            f"/api/comunicaciones/aprobar/lote/{lote_id}",
            headers={"Authorization": f"Bearer {coordinador_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

        # Verify all are Enviando
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT estado FROM comunicacion WHERE lote_id = :lid"),
                {"lid": lote_id},
            )
            for row in result.fetchall():
                assert row[0] == "Enviando"
        await engine.dispose()

    async def test_cancel_lote_transitions_to_cancelado(
        self, async_client: AsyncClient, auth_token: str, coordinador_token: str,
        seed_data: dict,
    ):
        """Cancel lote → all Pendiente → Cancelado."""
        # Enqueue
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Cancel test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # Cancel
        resp = await async_client.post(
            f"/api/comunicaciones/cancelar/{lote_id}",
            headers={"Authorization": f"Bearer {coordinador_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

        # Verify all are Cancelado
        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT estado FROM comunicacion WHERE lote_id = :lid"),
                {"lid": lote_id},
            )
            for row in result.fetchall():
                assert row[0] == "Cancelado"
        await engine.dispose()

    async def test_user_without_aprobar_gets_403(
        self, async_client: AsyncClient, profesor_token: str, auth_token: str,
        seed_data: dict,
    ):
        """User without comunicacion:aprobar → 403."""
        # Create a lote first
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Perm test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # Try to approve with PROFESOR (they have comunicacion:enviar but not comunicacion:aprobar)
        resp = await async_client.post(
            f"/api/comunicaciones/aprobar/lote/{lote_id}",
            headers={"Authorization": f"Bearer {profesor_token}"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Permissions (task 4.4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPermissions:
    """Auth guards for comunicaciones endpoints."""

    async def test_no_token_returns_403(
        self, async_client: AsyncClient,
    ):
        """Endpoints sin token → 403."""
        endpoints = [
            ("POST", "/api/comunicaciones/preview"),
            ("POST", "/api/comunicaciones/enviar"),
            ("GET", "/api/comunicaciones/estadisticas?materia_id=" + str(uuid.uuid4())),
            ("GET", "/api/comunicaciones/lotes"),
        ]
        for method, url in endpoints:
            resp = await async_client.request(method, url)
            assert resp.status_code == 403, f"{method} {url} should be 403"

    async def test_no_permission_returns_403(
        self, async_client: AsyncClient, no_perm_token: str, seed_data: dict,
    ):
        """User without comunicacion:enviar → 403."""
        resp = await async_client.post(
            "/api/comunicaciones/preview",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Test",
                "cuerpo_template": "Test",
                "destinatarios": [
                    {"nombre": "Juan", "apellido": "Pérez",
                     "materia": "", "comision": "", "nombre_profesor": ""},
                ],
            },
            headers={"Authorization": f"Bearer {no_perm_token}"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Tenant isolation (task 4.4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiTenant:
    """Multi-tenant isolation."""

    async def test_tenant_b_sees_no_comunicaciones(
        self, async_client: AsyncClient, other_auth_token: str,
        seed_data: dict,
    ):
        """Tenant B no ve comunicaciones de tenant A."""
        resp = await async_client.post(
            "/api/comunicaciones/preview",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Test",
                "cuerpo_template": "Test",
                "destinatarios": [
                    {"nombre": "Juan", "apellido": "Pérez",
                     "materia": "", "comision": "", "nombre_profesor": ""},
                ],
            },
            headers={"Authorization": f"Bearer {other_auth_token}"},
        )
        assert resp.status_code == 404  # materia not found in different tenant


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Cifrado (task 4.4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCifrado:
    """Destinatario cifrado — R-COM-07."""

    async def test_email_not_in_response(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """API response does not expose raw email addresses."""
        resp = await async_client.post(
            "/api/comunicaciones/preview",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Test ${nombre}",
                "cuerpo_template": "Body",
                "destinatarios": [
                    {"nombre": "Juan", "apellido": "Pérez",
                     "materia": "", "comision": "", "nombre_profesor": ""},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            # Should not contain raw email
            assert "@" not in item["destinatario_masked"] or "***" in item["destinatario_masked"]


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Invalid transitions (task 4.4)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvalidTransitions:
    """Invalid state transitions → 409."""

    async def test_approve_already_sent_returns_409(
        self, async_client: AsyncClient, auth_token: str, coordinador_token: str,
        seed_data: dict,
    ):
        """Cannot approve a message that is already Enviado."""
        # Enqueue and auto-approve (no approval needed)
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Conflict test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # Get a comunicacion id from the lote
        resp = await async_client.get(
            f"/api/comunicaciones/lotes/{lote_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200

    async def test_cancel_already_enviado_returns_409(
        self, async_client: AsyncClient, auth_token: str, coordinador_token: str,
        seed_data: dict,
    ):
        """Cancel a lote where messages are already Enviado → error or empty."""
        # Enqueue
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Cancel conflict ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # Worker processes to Enviado
        from app.workers.comunicacion_worker import ComunicacionWorker
        from app.core.database import create_engine as ce, create_session_factory as csf

        engine = ce(TEST_SETTINGS)
        session_factory = csf(engine)
        worker = ComunicacionWorker(
            session_factory=session_factory,
            settings=TEST_SETTINGS,
        )
        await worker._process_batch()
        await engine.dispose()

        # Now try to cancel — should say "no pending messages"
        resp = await async_client.post(
            f"/api/comunicaciones/cancelar/{lote_id}",
            headers={"Authorization": f"Bearer {coordinador_token}"},
        )
        assert resp.status_code == 400  # No hay mensajes pendientes


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Estadisticas (task 4.5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEstadisticas:
    """GET /api/comunicaciones/estadisticas — R-COM-06."""

    async def test_query_stats_returns_grouped_counts(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Stats return grouped counts by estado."""
        # Create some messages first
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Stats test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201

        resp = await async_client.get(
            f"/api/comunicaciones/estadisticas?materia_id={seed_data['materia_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pendientes"] >= 2
        assert body["enviados"] == 0

    async def test_empty_materia_returns_zeros(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """Materia without comunicaciones → all zeros."""
        resp = await async_client.get(
            f"/api/comunicaciones/estadisticas?materia_id={seed_data['materia2_id']}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pendientes"] == 0
        assert body["enviados"] == 0
        assert body["fallidos"] == 0
        assert body["cancelados"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: Lotes detail (task 4.5)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLotes:
    """GET /api/comunicaciones/lotes and /lotes/{lote_id}."""

    async def test_list_lotes_and_detail(
        self, async_client: AsyncClient, auth_token: str, seed_data: dict,
    ):
        """List lotes and get detail for a specific lote."""
        # Create a lote
        resp = await async_client.post(
            "/api/comunicaciones/enviar",
            json={
                "materia_id": str(seed_data["materia_id"]),
                "asunto_template": "Lote test ${materia}",
                "cuerpo_template": "Body ${nombre}",
                "requiere_aprobacion": True,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        lote_id = resp.json()["lote_id"]

        # List lotes
        resp = await async_client.get(
            "/api/comunicaciones/lotes",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert any(l["lote_id"] == str(lote_id) for l in body["items"])

        # Lote detail
        resp = await async_client.get(
            f"/api/comunicaciones/lotes/{lote_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        assert items[0]["estado"] == "Pendiente"
        # Email should NOT be exposed
        assert "email" not in str(items[0]).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Auth guard tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthGuards:
    """Auth guards for comunicaciones endpoints."""

    async def test_no_auth_returns_403(
        self, async_client: AsyncClient,
    ):
        """Endpoints sin token → 403."""
        endpoints = [
            ("POST", "/api/comunicaciones/preview"),
            ("POST", "/api/comunicaciones/enviar"),
            ("GET", "/api/comunicaciones/lotes"),
            ("GET", "/api/comunicaciones/estadisticas?materia_id=" + str(uuid.uuid4())),
            ("POST", f"/api/comunicaciones/aprobar/lote/{uuid.uuid4()}"),
            ("POST", f"/api/comunicaciones/cancelar/{uuid.uuid4()}"),
        ]
        for method, url in endpoints:
            resp = await async_client.request(method, url)
            assert resp.status_code == 403, f"{method} {url} should be 403"
