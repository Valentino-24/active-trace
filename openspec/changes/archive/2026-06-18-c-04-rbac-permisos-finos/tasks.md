## 1. Modelos RBAC

- [x] 1.1 Crear `app/models/rbac.py` con modelos `Role` (nombre, codigo único por tenant, descripción), `Permission` (codigo `modulo:accion` único por tenant, descripción), `RolePermission` (role_id FK, permission_id FK, unique compuesto), `UserRole` (user_id FK, role_id FK, desde date, hasta date nullable) — todos heredan TenantScopedMixin y SoftDeleteMixin salvo RolePermission (relación pura, sin soft delete)
- [x] 1.2 Actualizar `app/models/__init__.py` para re-exportar Role, Permission, RolePermission, UserRole

## 2. Actualizar modelo User con relación a roles

- [x] 2.1 Agregar a `app/models/user.py` la relación `roles: list[UserRole]` y propiedad `permissions: set[str]` que resuelve permisos efectivos (unión de roles vigentes)

## 3. Resolución de permisos

- [x] 3.1 Implementar en `core/permissions.py`: función `get_user_permissions(db, user) -> set[str]` que consulta UserRoles vigentes → RolePermissions → Permissions y devuelve set de códigos

## 4. Guard require_permission

- [x] 4.1 Actualizar `core/dependencies.py`: modificar `get_current_user` para que cargue también los permisos del usuario (usando get_user_permissions) y los incluya en el objeto User
- [x] 4.2 Implementar `require_permission(permiso: str)` como factory de dependency en `core/permissions.py`: verifica que el permiso esté en user.permissions, si no → HTTPException(403)

## 5. Migración Alembic

- [x] 5.1 Crear `alembic/versions/003_crear_rbac.py`: create tables role, permission, role_permission, user_role
- [x] 5.2 Agregar seed data: INSERT de los 7 roles del dominio (ALUMNO, TUTOR, PROFESOR, COORDINADOR, NEXO, ADMIN, FINANZAS)
- [x] 5.3 Agregar seed data: INSERT de todos los permisos de la matriz §3.3 de `03_actores_y_roles.md` (~30 permisos)
- [x] 5.4 Agregar seed data: INSERT de las relaciones role_permission según la matriz
- [x] 5.5 Verificar migración offline — SQL generado correctamente
- [x] 5.6 Verificar downgrade — DROP TABLE correcto

## 6. Tests

- [x] 6.1 (RED) Escribir `tests/test_rbac_models.py`: estructura Role (3 tests), Permission (2), RolePermission (2), UserRole (3) — incluyendo unique constraints, timestamps, soft delete
- [x] 6.2 (GREEN) Ajustar modelos hasta que los tests estructurales pasen
- [x] 6.3 (RED) Escribir `tests/test_permissions.py`: get_user_permissions — unión de roles (2 tests), vigencia (2 tests), sin roles (1 test), permiso directo (1 test)
- [x] 6.4 (GREEN) Implementar resolución de permisos hasta que tests pasen
- [x] 6.5 (TRIANGULATE) Escribir `tests/test_require_permission.py` con async_client: endpoint protegido con permiso → 200, sin permiso → 403, sin auth → 401
- [x] 6.6 (TRIANGULATE) Test de asignación vencida: user con rol vencido no tiene los permisos

## 7. Verificación final

- [x] 7.1 Ejecutar suite completa de tests y confirmar verde
- [x] 7.2 Confirmar que ningún archivo .py supera 500 LOC
