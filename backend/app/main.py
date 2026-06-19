"""activia-trace — FastAPI application entrypoint.

Creates the application via create_app() factory for both
production (uvicorn) and test (httpx AsyncClient) usage.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routers.avisos import router as avisos_router
from app.api.v1.routers.tareas import router as tareas_router
from app.api.v1.routers.programas_fechas import router as programas_fechas_router
from app.api.v1.routers.liquidaciones import router as liquidaciones_router
from app.api.v1.routers.auditoria import router as auditoria_router
from app.api.v1.routers.perfil_inbox import router as perfil_inbox_router
from app.api.v1.routers.admin.carreras import router as admin_carreras_router
from app.api.v1.routers.admin.cohortes import router as admin_cohortes_router
from app.api.v1.routers.admin.dictados import router as admin_dictados_router
from app.api.v1.routers.admin.materias import router as admin_materias_router
from app.api.v1.routers.admin.usuarios import router as admin_usuarios_router
from app.api.v1.routers.asignaciones import router as asignaciones_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.equipos import router as equipos_router
from app.api.v1.routers.padron import router as padron_router
from app.api.v1.routers.analisis import router as analisis_router
from app.api.v1.routers.calificaciones import router as calificaciones_router
from app.api.v1.routers.comunicaciones import router as comunicaciones_router
from app.api.v1.routers.encuentros import router as encuentros_router
from app.api.v1.routers.guardias import router as guardias_router
from app.api.v1.routers.coloquios import router as coloquios_router
from app.api.v1.routers.health import router as health_router
from app.core.config import Settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import setup_logging
from app.core.observability import instrument_fastapi, setup_observability
from app.workers.comunicacion_worker import ComunicacionWorker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: engine creation and cleanup.

    Creates the async engine and session factory on startup,
    disposes the engine on shutdown.
    """
    settings: Settings = app.state.settings

    # ── Engine & session factory ──────────────────────────────────────
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.async_session_factory = session_factory
    app.state.engine = engine

    # ── Observability ─────────────────────────────────────────────────
    if settings.otel_service_name:
        setup_observability(
            service_name=settings.otel_service_name,
            otlp_endpoint=settings.otel_exporter_otlp_endpoint,
        )
        instrument_fastapi(app)

    # ── ComunicacionWorker ─────────────────────────────────────────────────
    worker = ComunicacionWorker(
        session_factory=session_factory,
        settings=settings,
    )
    worker_task = asyncio.create_task(worker.run())
    app.state.worker_task = worker_task

    logger.info("Application started")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    logger.info("Shutting down ComunicacionWorker...")
    await worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("ComunicacionWorker stopped")

    await engine.dispose()
    logger.info("Application shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Factory to create a configured FastAPI application.

    Args:
        settings: Optional Settings instance. If None, loads from env/.env.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = Settings()  # type: ignore[call-arg]

    app = FastAPI(
        title="activia-trace",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings in app state for lifespan and dependency access
    app.state.settings = settings

    # ── Logging ────────────────────────────────────────────────────────
    setup_logging()

    # ── Routers ────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(admin_carreras_router, prefix="/api/admin/carreras")
    app.include_router(admin_cohortes_router, prefix="/api/admin/cohortes")
    app.include_router(admin_materias_router, prefix="/api/admin/materias")
    app.include_router(admin_dictados_router, prefix="/api/admin/dictados")
    app.include_router(admin_usuarios_router, prefix="/api/admin/usuarios")
    app.include_router(asignaciones_router, prefix="/api/asignaciones")
    app.include_router(equipos_router, prefix="/api/equipos")
    app.include_router(padron_router, prefix="/api/padron")
    app.include_router(analisis_router)
    app.include_router(calificaciones_router)
    app.include_router(comunicaciones_router)
    app.include_router(encuentros_router)
    app.include_router(guardias_router)
    app.include_router(coloquios_router)
    app.include_router(avisos_router)
    app.include_router(tareas_router)
    app.include_router(programas_fechas_router)
    app.include_router(liquidaciones_router)
    app.include_router(auditoria_router)
    app.include_router(perfil_inbox_router)

    return app


# ── Module-level app for uvicorn (production) ────────────────────────────
# The app variable is created at import time for uvicorn's benefit.
# In tests, import create_app() directly instead of relying on this.
try:
    app = create_app()
except Exception as exc:
    import logging
    logging.warning("Could not create app at import time: %s", exc)
    app = None  # type: ignore[assignment]
