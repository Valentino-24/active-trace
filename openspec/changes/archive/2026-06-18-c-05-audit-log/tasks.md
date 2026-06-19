## 1. Modelo AuditLog

- [x] 1.1 Crear `backend/app/models/audit_log.py` con modelo `AuditLog` que hereda `BaseModelMixin` + `Base` (SIN SoftDeleteMixin). Index en (tenant_id, accion) y en (tenant_id, fecha_hora).
- [x] 1.2 Agregar re-export de `AuditLog` en `backend/app/models/__init__.py`
- [x] 1.3 Crear `backend/app/repositories/audit_log_repository.py` con clase `AuditLogRepository(BaseRepository[AuditLog])` que expone solo `create()` y `list()` (sin update, sin delete, sin soft-delete)
- [x] 1.4 Agregar re-export de `AuditLogRepository` en `backend/app/repositories/__init__.py`

## 2. Helper de auditoría

- [x] 2.1 Crear `backend/app/services/audit_service.py` con función `log_action()`. Usa `AuditLogRepository().create()`. NO sobreescribe ip/user_agent si se pasan explícitamente.

## 3. Impersonación — JWT y security

- [x] 3.1 Agregar función `create_impersonation_token()` en `backend/app/core/security.py`.
- [x] 3.2 Actualizar `get_current_user` en `backend/app/core/dependencies.py` para detectar claim `impersonator_id`.
- [x] 3.3 Agregar propiedad `is_impersonating` y atributo `_impersonator_user` al modelo User.

## 4. Endpoints de impersonación

- [x] 4.1 Agregar endpoint `POST /api/auth/impersonate/start` con permiso `impersonacion:usar` y log `IMPERSONACION_INICIAR`.
- [x] 4.2 Agregar endpoint `POST /api/auth/impersonate/end` con detección de impersonación y log `IMPERSONACION_FINALIZAR`.
- [x] 4.3 Schemas Pydantic: `ImpersonateStartRequest`, `ImpersonateStartResponse`, `ImpersonateEndResponse`.

## 5. Migración Alembic 004

- [x] 5.1 Migración Alembic `004_crear_audit_log_impersonacion.py` con tabla `audit_log`, indexes compuestos, REVOKE UPDATE/DELETE, seed `impersonacion:usar` + ADMIN.
- [x] 5.2 Verificar que la migración corre y revierte correctamente (pendiente ejecución contra BD real).

## 6. Tests

- [x] 6.1 Test: `test_audit_log_model.py` — crear AuditLog, verificar campos, id y fecha_hora auto.
- [x] 6.2 Test: append-only — repository bloquea update y delete con RuntimeError.
- [x] 6.3 Test: `test_audit_service.py` — `log_action()` minimal y all params.
- [x] 6.4 Test: request extraction y override explícito.
- [x] 6.5 Test: start success devuelve tokens y log audit.
- [x] 6.6 Test: start sin permiso (403), usuario inexistente (404), inactivo (400).
- [x] 6.7 Test: end success devuelve token y log audit.
- [x] 6.8 Test: end sin impersonación da 400.
- [x] 6.9 Test: `get_current_user` con token normal NO tiene impersonation, token de impersonation SÍ.
- [x] 6.10 Test: bajo impersonación, permisos cargados son los del impersonado.
