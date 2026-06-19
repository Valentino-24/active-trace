## Why

C-03 habilitó la autenticación: sabemos QUIÉN es el usuario. Pero sin RBAC no sabemos QUÉ puede hacer. Cada endpoint de negocio necesita un guard que verifique permisos antes de ejecutar. Este change implementa el sistema completo de autorización: roles, permisos finos `modulo:accion`, la matriz rol×permiso como datos administrables y el guard `require_permission` que protege cada endpoint.

Sin C-04, ningún endpoint de negocio (C-06 en adelante) puede operar con seguridad. Es el segundo gate del camino crítico.

## What Changes

- **Nuevos modelos**: `Role` (catálogo de roles del dominio), `Permission` (catálogo de permisos `modulo:accion`), `RolePermission` (matriz N:N rol×permiso), `UserRole` (asignación rol→usuario con vigencia).
- **Seed data**: los 7 roles del dominio (ALUMNO, TUTOR, PROFESOR, COORDINADOR, NEXO, ADMIN, FINANZAS) y la matriz completa de permisos de `03_actores_y_roles.md §3.3`.
- **`core/permissions.py`**: se completa con el guard `require_permission("modulo:accion")` como dependency de FastAPI.
- **Resolución de permisos**: función que calcula los permisos efectivos de un usuario (unión de roles, acotada por tenant y vigencia de asignaciones).
- **Migración Alembic 003**: tablas role, permission, role_permission, user_role + seed de roles y matriz base.
- **Tests**: usuario sin permiso → 403, unión de roles, permiso `(propio)` vs global, catálogo administrable.

## Capabilities

### New Capabilities
- `rbac-core`: Sistema de roles, permisos finos (`modulo:accion`), matriz rol×permiso administrable, asignación de roles a usuarios con vigencia, y guard `require_permission` para endpoints.

### Modified Capabilities
- *(ninguna — primer change de autorización)*

## Impact

- **Tres nuevos modelos admin**: `Role` (nombre, codigo único), `Permission` (codigo `modulo:accion` único, descripción), `RolePermission` (role_id FK, permission_id FK).
- **Un nuevo modelo de asignación**: `UserRole` (user_id FK, role_id FK, desde, hasta nullable) — hereda de TenantScopedMixin.
- **core/permissions.py**: se completa con `require_permission(permiso: str)` como dependency de FastAPI que usa `get_current_user` para obtener el usuario y verifica si tiene el permiso.
- **core/dependencies.py**: se agrega `get_current_user_with_permissions` o se actualiza `get_current_user` para incluir permisos.
- **Seed data**: migración con INSERT de los 7 roles y ~30 permisos de la matriz base.
- **User model**: se agrega relación `roles` (acceso a UserRole → Role → Permission).
- **Tests**: cobertura de guard con/ sin permiso, unión de roles, filtro por vigencia, administración del catálogo.
- **BREAKING**: `get_current_user` ahora debe cargar también los permisos. Los tests existentes de C-03 pueden necesitar ajustes.
