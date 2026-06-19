## 1. Migración de base de datos (006)

- [ ] 1.1 Crear `006_extender_usuario_crear_asignacion.py`: añadir columnas PII a `users` (nombre, apellidos, dni, cuil, cbu, alias_cbu, banco, regional, legajo, legajo_profesional, facturador, estado, email_hash)
- [ ] 1.2 Modificar columna `email` existente para almacenar cifrado (pasa a `Text` nullable para migración)
- [ ] 1.3 Crear tabla `asignaciones` con columnas: id, tenant_id, usuario_id, rol, materia_id (nullable), carrera_id (nullable), cohorte_id (nullable), comisiones (JSONB/Text[]), responsable_id (nullable), desde (date), hasta (date, nullable), created_at, updated_at, deleted_at
- [ ] 1.4 Migrar emails existentes: leer cada user, cifrar email con AES-256-GCM, calcular email_hash, guardar ciphertext + hash en la misma transacción
- [ ] 1.5 Agregar índices y constraints: uq_asignacion_tenant_usuario_rol_contexto (unique compuesto), ix_users_email_hash, ix_asignaciones_usuario_id

## 2. Modelos SQLAlchemy

- [ ] 2.1 Extender `User` model: agregar columnas PII + email_hash + método para encriptar/desencriptar email + property `estado_vigencia` (futuro)
- [ ] 2.2 Crear `Asignacion` model con TenantScopedMixin, SoftDeleteMixin, columnas de contexto, property `estado_vigencia` derivado, relationship a User (usuario y responsable)

## 3. Schemas Pydantic (DTOs con cifrado)

- [ ] 3.1 Crear `UserCreate`, `UserUpdate`, `UserResponse`, `UserListResponse` con cifrado/descifrado de PII en `model_validator`/`model_serializer`
- [ ] 3.2 Crear `AsignacionCreate`, `AsignacionUpdate`, `AsignacionResponse`, `AsignacionListResponse` con `estado_vigencia` calculado

## 4. Repositorios

- [ ] 4.1 Extender `UserRepository`: `get_by_email_hash()`, `create_with_pii()`, `update_with_pii()`, filtros por estado, paginación
- [ ] 4.2 Crear `AsignacionRepository`: CRUD con tenant-scoping, `revoke()` (set hasta=today), filtros por materia/usuario/rol/vigencia

## 5. Routers

- [ ] 5.1 Crear `backend/app/api/v1/routers/admin/usuarios.py`: GET list, POST create, GET by id, PATCH update — todos protegidos con permisos `usuarios:*`
- [ ] 5.2 Crear `backend/app/api/v1/routers/asignaciones.py`: GET list con filtros, POST create, DELETE revoke — protegidos con `equipos:*`
- [ ] 5.3 Registrar ambos routers en `main.py` (prefixes `/api/admin/usuarios` y `/api/asignaciones`)

## 6. Permisos y seed

- [ ] 6.1 Agregar 5 permisos nuevos al seed de permisos: `usuarios:list`, `usuarios:create`, `usuarios:update`, `equipos:asignar`, `equipos:revocar`
- [ ] 6.2 Asignar permisos `usuarios:*` al rol ADMIN, permisos `equipos:*` a ADMIN y COORDINADOR

## 7. Adaptación auth service

- [ ] 7.1 Modificar `authenticate_user` en `auth_service.py` para buscar por `email_hash` (hash del input) en lugar de email texto plano
- [ ] 7.2 Verificar que el login funciona con email cifrado + hash

## 8. Tests

- [ ] 8.1 Tests de repositorio: UserRepository create/list/update con PII cifrada, AsignacionRepository create/revoke/list/filtros
- [ ] 8.2 Tests de integración: endpoints de usuarios CRUD (crear, listar, obtener, actualizar, desactivar, duplicados, multi-tenant)
- [ ] 8.3 Tests de integración: endpoints de asignaciones (crear, listar con filtros, revocar, idempotencia, multi-tenant, permisos)
- [ ] 8.4 Tests de auth: login con email cifrado funciona, login con email incorrecto falla
