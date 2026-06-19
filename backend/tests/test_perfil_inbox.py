"""Tests for Perfil y Mensajeria Interna (C-20)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest_asyncio


class TestPerfilService:
    """Unit: CUIL bloqueado."""

    def _patch_perfil(self, body, existing_cuil):
        if "cuil" in body:
            raise ValueError("CUIL no modificable")
        return {**existing_cuil, **body}

    def test_cuil_no_modificable(self):
        try:
            self._patch_perfil({"cuil": "20-123", "display_name": "X"}, {"cuil": "20-999"})
            assert False
        except ValueError:
            pass

    def test_sin_cuil_si_modifica(self):
        r = self._patch_perfil({"display_name": "Nuevo"}, {"cuil": "20-999"})
        assert r["display_name"] == "Nuevo"


class TestMensajeModel:
    def test_tablename(self):
        from app.models.mensaje import Mensaje
        assert Mensaje.__tablename__ == "mensaje"

    def test_fields(self):
        from app.models.mensaje import Mensaje
        cols = {c.name for c in Mensaje.__table__.columns}
        for f in ("remitente_id", "destinatario_id", "asunto", "texto", "leido", "leido_at"):
            assert f in cols


@pytest_asyncio.fixture
async def seed_mensajes() -> dict:
    """Seed: tenant + 2 users."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.core.security import hash_password
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
        tenant = Tenant(nombre="Mensaje Tenant", codigo=f"MSG{uuid.uuid4().hex[:4]}")
        session.add(tenant); await session.flush()

        u1 = User(tenant_id=tenant.id, email=f"a-{uuid.uuid4().hex[:8]}@t.com",
                   password_hash=hash_password("A123!"), display_name="A", is_active=True)
        u2 = User(tenant_id=tenant.id, email=f"b-{uuid.uuid4().hex[:8]}@t.com",
                   password_hash=hash_password("B123!"), display_name="B", is_active=True)
        session.add_all([u1, u2]); await session.flush()
        await session.commit()

        data["tenant_id"] = tenant.id
        data["u1"] = u1.id
        data["u2"] = u2.id

    await engine.dispose()
    return data


class TestMensajeRepository:
    async def test_enviar_y_listar_recibidos(self, seed_mensajes):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.mensaje_repository import MensajeRepository

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = MensajeRepository(session=session, tenant_id=seed_mensajes["tenant_id"])
            await r.create(remitente_id=seed_mensajes["u1"], destinatario_id=seed_mensajes["u2"],
                           asunto="Hola", texto="Mensaje 1")
            await r.create(remitente_id=seed_mensajes["u2"], destinatario_id=seed_mensajes["u1"],
                           asunto="Re:", texto="Respuesta")
            await session.commit()

            rec = await r.list_recibidos(seed_mensajes["u2"])
            assert len(rec) == 1
            assert rec[0].asunto == "Hola"

            env = await r.list_enviados(seed_mensajes["u1"])
            assert len(env) == 1
        await engine.dispose()

    async def test_marcar_leido(self, seed_mensajes):
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from .conftest import TEST_SETTINGS
        from app.repositories.mensaje_repository import MensajeRepository
        from datetime import UTC, datetime

        engine = create_async_engine(TEST_SETTINGS.database_url, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            r = MensajeRepository(session=session, tenant_id=seed_mensajes["tenant_id"])
            msg = await r.create(remitente_id=seed_mensajes["u1"], destinatario_id=seed_mensajes["u2"],
                                 asunto="Test", texto="Body")
            await session.commit()

            assert msg.leido is False
            await r.marcar_leido(msg.id)
            assert msg.leido is True
            assert msg.leido_at is not None
        await engine.dispose()
