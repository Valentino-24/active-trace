"""Repositories — data access layer with multi-tenant isolation.

Every concrete repository inherits from BaseRepository[T] which
enforces tenant_id scoping on all queries.
"""

from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.base import BaseRepository
from app.repositories.carrera_repository import CarreraRepository
from app.repositories.cohorte_repository import CohorteRepository
from app.repositories.dictado_repository import DictadoRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "AuditLogRepository",
    "CarreraRepository",
    "CohorteRepository",
    "MateriaRepository",
    "DictadoRepository",
]
