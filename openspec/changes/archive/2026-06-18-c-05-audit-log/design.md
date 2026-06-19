## Context

El nombre del producto es *trace* — todo audita. C-04 dejó el RBAC listo con permisos finos (`modulo:accion`) y el permiso `impersonacion:usar` ya seedeado. Lo que falta:
- Un modelo `AuditLog` append-only que registre inmutablemente cada acción significativa.
- Un helper de auditoría que capture IP, user_agent, y detalles contextuales automáticamente.
- Un mecanismo de impersonación con sesión JWT distinguible, endpoints start/end, y registro en audit log.

El log de auditoría (E-AUD en la KB) es el corazón de la trazabilidad. Sin él, el sistema no cumple su promesa fundacional.

## Goals / Non-Goals

**Goals:**
- Modelo `AuditLog` append-only (sin update, sin delete, sin soft-delete) con todos los campos de E-AUD.
- Helper `log_action()` que centralice la creación de registros con contexto de request.
- Impersonación con endpoints `POST /auth/impersonate/start` y `POST /auth/impersonate/end`.
- JWT con claim `impersonator_id` para sesiones bajo impersonación.
- `get_current_user` actualizado para exponer `is_impersonating` e `impersonated_user`.
- Migración Alembic 004 con tabla `audit_log` y restricciones a nivel DB.
- Tests de append-only (rechazar update/delete), atribución bajo impersonación, y registro con código + filas.

**Non-Goals:**
- NO incluir lógica de negocio específica de cada módulo (calificaciones, comunicaciones, etc.). Eso se hará en cada change respectivo usando el helper `log_action()`.
- NO implementar un dashboard de auditoría (frontend). Eso será parte de un change futuro de reporting.
- NO implementar catálogo completo de códigos de acción (se irá poblando según se usen en cada change).

## Decisions

### 1. AuditLog SIN SoftDeleteMixin — append-only puro
**Contexto:** Todos los modelos actuales usan `SoftDeleteMixin`. AuditLog es la excepción: ningún registro puede borrarse ni lógica ni físicamente.
**Decisión:** AuditLog hereda solo `BaseModelMixin` (id, created_at, updated_at). `updated_at` se deja por consistencia técnica pero nunca cambia porque no hay update.
**Alternativa considerada:** Usar soft-delete con trigger que lo impida → complejidad innecesaria.
**Implementación:** A nivel DB: `REVOKE UPDATE, DELETE ON audit_log TO app_user` en la migración. A nivel aplicación: repositorio expone solo `create()` y `list()`.

### 2. Helper `log_action()` como función, no servicio con clase
**Contexto:** `AuthService` usa clase con session y tenant_id en `__init__`. Audit logging es transversal y no siempre tiene un tenant_id asociado (ej: login fallido).
**Decisión:** `log_action()` es una función independiente en `app/services/audit_service.py` que recibe `db`, `actor_id` y contexto. No tiene estado interno.
**Alternativa considerada:** Middleware automático para toda request → demasiado ruido. Mejor que cada módulo llame `log_action()` explícitamente cuando realiza una acción significativa.

### 3. Impersonación vía JWT con claim `impersonator_id`
**Contexto:** La sesión bajo impersonación necesita distinguir al actor real (quien impersona) del usuario impersonado.
**Decisión:** Cuando un admin con `impersonacion:usar` inicia impersonación, se genera un JWT especial con `sub` = user_id del impersonado y `impersonator_id` = user_id del actor real. `get_current_user` detecta este claim, resuelve ambos usuarios, y expone:
- `current_user.id` → el user_id del impersonado (identidad efectiva)
- `current_user.is_impersonating = True`
- `current_user.impersonated_user` = el mismo usuario (la identidad efectiva es el impersonado)
- Almacena el `impersonator_user` en atributo interno
**Alternativa considerada:** Mantener sesión original + header de impersonación → inseguro, el cliente puede manipularlo.
**Alternativa considerada:** Dos JWTs (original + tag de impersonación) → complejidad innecesaria.

### 4. IP y User-Agent capturados en el router y pasados al servicio
**Contexto:** FastAPI expone `request.client.host` y `request.headers.get("user-agent")` en los handlers.
**Decisión:** Cada endpoint que llame a `log_action()` recibe `request: Request` como dependencia opcional y extrae IP y user-agent. El helper extrae estos valores automáticamente si se le pasa el request.
**Alternativa considerada:** Middleware que registre toda request → demasiado ruido, no toda request es una "acción significativa".

## Risks / Trade-offs

- **[Rendimiento]** Insertar en audit_log por cada acción significativa agrega latency a la request. → **Mitigación:** El insert es en la misma transacción que la acción principal. Si la acción principal falla, el rollback también revierte el audit_log. Esto es correcto: no se auditan acciones fallidas.
- **[Seguridad]** Que un atacante inunde el audit_log con registros. → **Mitigación:** No hay límite de tamaño en el diseño base. Se podría agregar rotación o archive futuro. Por ahora el beneficio de tener todo auditado supera el riesgo.
- **[Complejidad]** `get_current_user` con impersonación añade un caso borde. → **Mitigación:** Solo se activa si el claim `impersonator_id` está presente. Los tokens normales siguen funcionando sin cambios.
- **[Consistencia]** `impersonado_id` nullable en AuditLog para acciones NO bajo impersonación. → La mayoría de registros tendrán `impersonado_id = NULL`. Es correcto: no hay penalidad de storage significativa.
