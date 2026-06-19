"""Admin routers — protected endpoints for academic structure and users.

Routers are aggregated here and mounted in main.py under /api/admin/.
"""

from app.api.v1.routers.admin.carreras import router as carreras_router
from app.api.v1.routers.admin.cohortes import router as cohortes_router
from app.api.v1.routers.admin.dictados import router as dictados_router
from app.api.v1.routers.admin.materias import router as materias_router
from app.api.v1.routers.admin.usuarios import router as usuarios_router

__all__ = [
    "carreras_router",
    "cohortes_router",
    "materias_router",
    "dictados_router",
    "usuarios_router",
]
