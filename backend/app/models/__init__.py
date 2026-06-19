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
    "BaseModelMixin",
    "TenantScopedMixin",
    "SoftDeleteMixin",
]
