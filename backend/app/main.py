"""activia-trace — FastAPI application entrypoint.

Creates the application via create_app() factory for both
production (uvicorn) and test (httpx AsyncClient) usage.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routers.admin.carreras import router as admin_carreras_router
from app.api.v1.routers.admin.cohortes import router as admin_cohortes_router
from app.api.v1.routers.admin.dictados import router as admin_dictados_router
from app.api.v1.routers.admin.materias import router as admin_materias_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.health import router as health_router
from app.core.config import Settings
from app.core.database import create_engine, create_session_factory
from app.core.logging import setup_logging
from app.core.observability import instrument_fastapi, setup_observability

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

    logger.info("Application started")
    yield
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
