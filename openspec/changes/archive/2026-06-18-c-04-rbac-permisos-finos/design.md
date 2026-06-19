## Context

Activia-trace tiene autenticación (C-03): sabemos quién es el usuario y a qué tenant pertenece. Pero no tenemos autorización: cualquier usuario autenticado puede llamar cualquier endpoint. Este change implementa RBAC con permisos finos `modulo:accion`, roles administrables, asignación con vigencia, y el guard `require_permission` que protege cada endpoint.

C-03 dejó: `get_current_user` (resuelve User desde JWT), modelo `User` con `is_active`, `core/security.py` con JWT utils, y `core/dependencies.py` con `get_db` y `get_current_user`. No existe aún el concepto de rol ni permiso.

## Goals / Non-Goals

**Goals:**
- Modelos `Role`, `Permission`, `RolePermission`, `UserRole` con tenant scope.
- Seed de 7 roles del dominio (ALUMNO, TUTOR, PROFESOR, COORDINADOR, NEXO, ADMIN, FINANZAS) y matriz de ~30 permisos base.
- Guard `require_permission("modulo:accion")` como dependency de FastAPI.
- Resolución de permisos efectivos (unión de roles del usuario, acotada por tenant y vigencia).
- Migración Alembic 003 con seed data.
- Tests: sin permiso → 403, unión de roles, vigencia, administración del catálogo.

**Non-Goals:**
- Frontend de administración de roles/permisos → C-21 (frontend shell) o change específico de UI.
- Endpoints REST para CRUD de roles/permisos (se crean solo los modelos y seed; los endpoints de administración van con el frontend).
- Impersonación → C-05 (audit-log).
- Permiso `(propio)` — se modela como permiso regular, la lógica de "solo propios datos" se implementa en cada endpoint de negocio.

## Decisions

### D1 — Modelo de datos RBAC

Cuatro tablas:

- **`role`** (catálogo): id UUID, nombre (e.g. "Profesor"), codigo (e.g. "PROFESOR") único, descripción, hereda TenantScopedMixin + SoftDeleteMixin.
- **`permission`** (catálogo): id UUID, codigo (e.g. "calificaciones:importar") único por tenant, descripción, hereda TenantScopedMixin + SoftDeleteMixin.
- **`role_permission`** (matriz N:N): role_id FK, permission_id FK, unique(role_id, permission_id). Sin soft delete (es una relación pura).
- **`user_role`** (asignación usuario→rol con vigencia): user_id FK, role_id FK, desde (date), hasta (date nullable), unique(user_id, role_id, desde). Hereda TenantScopedMixin + SoftDeleteMixin.

**Alternativa descartada**: meter permisos como JSONB en el rol. No permite queries eficientes de "qué roles tienen este permiso" ni auditoría.

### D2 — Resolución de permisos en `get_current_user`

`get_current_user` se actualiza para cargar también los permisos efectivos del usuario. El User object llevará una propiedad/set `permissions: set[str]` con los códigos de permiso (`modulo:accion`). Esto evita un query de permisos por cada endpoint.

La resolución hace:
1. Obtener los `UserRole` vigentes (desde <= hoy y (hasta IS NULL OR hasta >= hoy)) para el usuario.
2. Obtener los `Permission` asociados a esos roles vía `RolePermission`.
3. Unir en un set de strings `{permiso.codigo}`.

### D3 — `require_permission` como dependency parametrizada

```python
def require_permission(permiso: str):
    async def _require(user: User = Depends(get_current_user)) -> None:
        if permiso not in user.permissions:
            raise HTTPException(status_code=403, detail="Forbidden")
    return _require
```

Uso en endpoints:
```python
@router.get("/calificaciones")
async def list_calificaciones(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_permission("calificaciones:importar")),
):
    ...
```

### D4 — Seed data en migración

La migración 003 incluye:
1. Creación de tablas.
2. INSERT de los 7 roles.
3. INSERT de los permisos definidos en la matriz §3.3 de `03_actores_y_roles.md`.
4. INSERT de las relaciones role_permission según la matriz.

Esto es un seed inicial. En producción, los ADMIN pueden agregar/quitar permisos y roles vía endpoints de administración (a implementar en changes futuros).

### D5 — `(propio)` se maneja en cada endpoint

Los permisos marcados como `(propio)` en la matriz (e.g. `calificaciones:importar (propio)`) se modelan como un permiso regular. La verificación de "esto es tuyo o no" se hace en el service/endpoint de negocio comparando el user_id del recurso contra el user_id del JWT. No hay lógica RBAC para esto.

## Risks / Trade-offs

- **[Permisos cacheados en el User object pueden quedar stale si se cambian en medio de una request]** → Mitigación: los permisos se resuelven en cada request (vía `get_current_user`), no hay cache entre requests. El costo es un query por request, aceptable para MVP.
- **[Seed data hardcodeada en migración puede divergir del código]** → Mitigación: la matriz en `03_actores_y_roles.md` es la fuente de verdad. La migración debe reflejarla exactamente. Si cambia la KB, se crea una nueva migración.
- **[Sin endpoints CRUD de roles/permisos, la administración requiere SQL directo]** → Trade-off aceptado: los endpoints se agregan cuando haya frontend de administración (C-21+). Mientras tanto, se usa SQL vía migraciones.
