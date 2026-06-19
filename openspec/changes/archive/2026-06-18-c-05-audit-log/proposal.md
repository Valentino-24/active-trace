## Why

El nombre del producto es *trace* — todo audita. Sin un log de auditoría inmutable y append-only, no hay trazabilidad real de las acciones en el sistema. Cada importación de calificaciones, envío de comunicación, modificación de equipo docente o cierre de liquidación debe quedar registrado con quién, cuándo, desde dónde y sobre qué datos. Además, la impersonación (suplantación legítima para soporte) requiere un mecanismo de sesión distinguible y registro explícito de inicio y fin.

C-04 dejó el RBAC listo con el permiso `impersonacion:usar`. Este change implementa el audit log y la infraestructura de impersonación.

## What Changes

- **Nuevo modelo `AuditLog`** append-only: sin update ni delete a nivel aplicación y base de datos. Campos: actor_id, impersonado_id (nullable), materia_id (nullable), accion (código estandarizado), detalle (JSON), filas_afectadas, ip, user_agent, fecha_hora.
- **Helper/servicio de auditoría**: función `audit_log(db, actor, accion, ...)` que crea un registro y lo persiste.
- **Middleware de auditoría**: captura automática de IP y user_agent desde la request.
- **Impersonación**: endpoint `POST /api/auth/impersonate/start` y `POST /api/auth/impersonate/end`, sesión JWT distinguible con claim `impersonator_id`, auditoría de inicio y fin.
- **Dependency `get_current_user`**: se actualiza para soportar impersonación (resuelve quién es el actor real y quién el impersonado).
- **Migración Alembic 004**: tabla `audit_log`.
- Tests: append-only (update/delete rechazados), atribución bajo impersonación, registro de acción con código + filas afectadas.

## Capabilities

### New Capabilities
- `audit-log`: Registro inmutable append-only de acciones significativas con códigos estandarizados, captura automática de contexto (IP, user_agent), y helper de auditoría.
- `impersonation`: Suplantación legítima con sesión distinguible, permiso `impersonacion:usar`, registro de inicio/fin en audit log, y atribución de acciones al actor real.

### Modified Capabilities
- *(ninguna — primer change de auditoría e impersonación)*

## Impact

- **Nuevo modelo**: `AuditLog` con campos definidos en E-AUD de la KB. NO hereda SoftDeleteMixin (append-only) y las operaciones update/delete deben ser bloqueadas a nivel DB (triggers o permisos) y aplicación (repositorio de solo lectura + create).
- **Nuevo servicio**: `services/audit_service.py` con `log_action(db, actor_id, accion, detalle, filas_afectadas, materia_id=None, impersonado_id=None)`.
- **Nuevo middleware/helper**: captura de `request.client.host` e `request.headers.get("user-agent")` y los pasa al audit service.
- **core/dependencies.py**: `get_current_user` se actualiza para detectar si el JWT tiene claim `impersonator_id`. Si lo tiene, resuelve tanto al actor real (impersonator) como al impersonado. El objeto User expone `is_impersonating` y `impersonated_user`.
- **core/security.py**: se agrega `create_impersonation_token(user, impersonator)` que genera JWT con claim `impersonator_id`.
- **Router auth**: se agregan endpoints `POST /auth/impersonate/start` (requiere `impersonacion:usar`, recibe user_id a impersonar, devuelve token de impersonación) y `POST /auth/impersonate/end` (cierra impersonación, restaura sesión original).
- **core/permissions.py**: el permiso `impersonacion:usar` ya existe en el seed de C-04.
- **Migración Alembic 004**: create table `audit_log` sin soft-delete, con restricciones a nivel DB (revoke update/delete a la app).
- **BREAKING**: `get_current_user` ahora puede devolver un usuario en estado de impersonación. Los endpoints existentes deben funcionar igual (solo se agrega metadata, no cambia la identidad base).
