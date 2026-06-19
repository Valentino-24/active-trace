"""Domain models — re-exports for easy imports.

Usage:
    from app.models import Tenant, User, RefreshToken, PasswordResetToken, ...
"""

from app.models.audit_log import AuditLog
from app.models.auth import PasswordResetToken, RefreshToken
from app.models.base import BaseModelMixin, SoftDeleteMixin, TenantScopedMixin
from app.models.carrera import Carrera
from app.models.cohorte import Cohorte
from app.models.dictado import Dictado
from app.models.materia import Materia
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.tenant import Tenant
from app.models.asignacion import Asignacion
from app.models.user import User
from app.models.padron import EntradaPadron, VersionPadron
from app.models.calificacion import Calificacion
from app.models.comunicacion import Comunicacion, EstadoComunicacion
from app.models.umbral_materia import UmbralMateria
from app.models.slot_encuentro import SlotEncuentro
from app.models.instancia_encuentro import EstadoInstancia, InstanciaEncuentro
from app.models.guardia import EstadoGuardia, Guardia
from app.models.evaluacion import Evaluacion, TipoEvaluacion
from app.models.aviso import Aviso, AlcanceAviso, SeveridadAviso
from app.models.acknowledgment_aviso import AcknowledgmentAviso
from app.models.reserva_evaluacion import EstadoReserva, ReservaEvaluacion
from app.models.resultado_evaluacion import ResultadoEvaluacion

__all__ = [
    "Tenant",
    "User",
    "Asignacion",
    "VersionPadron",
    "EntradaPadron",
    "RefreshToken",
    "PasswordResetToken",
    "Role",
    "Permission",
    "RolePermission",
    "UserRole",
    "AuditLog",
    "Carrera",
    "Cohorte",
    "Materia",
    "Dictado",
    "Calificacion",
    "Comunicacion",
    "EstadoComunicacion",
    "UmbralMateria",
    "SlotEncuentro",
    "EstadoInstancia",
    "InstanciaEncuentro",
    "EstadoGuardia",
    "Guardia",
    "Evaluacion",
    "TipoEvaluacion",
    "ReservaEvaluacion",
    "EstadoReserva",
    "ResultadoEvaluacion",
    "Aviso",
    "AlcanceAviso",
    "SeveridadAviso",
    "AcknowledgmentAviso",
    "BaseModelMixin",
    "TenantScopedMixin",
    "SoftDeleteMixin",
]
