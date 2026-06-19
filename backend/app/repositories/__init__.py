"""Repositories — data access layer with multi-tenant isolation.

Every concrete repository inherits from BaseRepository[T] which
enforces tenant_id scoping on all queries.
"""

from app.repositories.analisis_repository import AnalisisRepository
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.base import BaseRepository
from app.repositories.calificacion_repository import CalificacionRepository
from app.repositories.comunicacion_repository import ComunicacionRepository
from app.repositories.umbral_repository import UmbralMateriaRepository
from app.repositories.carrera_repository import CarreraRepository
from app.repositories.cohorte_repository import CohorteRepository
from app.repositories.dictado_repository import DictadoRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.user_repository import UserRepository
from app.repositories.encuentro_repository import (
    SlotEncuentroRepository,
    InstanciaEncuentroRepository,
)
from app.repositories.guardia_repository import GuardiaRepository
from app.repositories.coloquio_repository import (
    EvaluacionRepository,
    ReservaEvaluacionRepository,
    ResultadoEvaluacionRepository,
)
from app.repositories.aviso_repository import AvisoRepository, AcknowledgmentRepository

__all__ = [
    "AnalisisRepository",
    "BaseRepository",
    "CalificacionRepository",
    "ComunicacionRepository",
    "UmbralMateriaRepository",
    "UserRepository",
    "AuditLogRepository",
    "CarreraRepository",
    "CohorteRepository",
    "MateriaRepository",
    "DictadoRepository",
    "SlotEncuentroRepository",
    "InstanciaEncuentroRepository",
    "GuardiaRepository",
    "EvaluacionRepository",
    "ReservaEvaluacionRepository",
    "ResultadoEvaluacionRepository",
    "AvisoRepository",
    "AcknowledgmentRepository",
]
