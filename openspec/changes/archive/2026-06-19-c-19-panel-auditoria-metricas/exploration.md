# Exploration: Panel de Auditoria y Metricas (C-19)

## Current State

`AuditLog` ya existe desde C-05. Es inmutable (append-only, sin soft delete). Campos: `fecha_hora`, `actor_id`, `accion`, `detalle` (JSON), `materia_id`, `filas_afectadas`, `ip`, `user_agent`. El repositorio solo expone `create()` y `list()` — update/delete bloqueados con RuntimeError.

No hay endpoints de consulta/analytics sobre AuditLog hoy. Los datos se escriben via `log_action()` en cada servicio pero no se consultan.

## Affected Areas

| File | Impact | Why |
|------|--------|-----|
| `app/models/audit_log.py` | Read | Sin cambios — modelo existente |
| `app/repositories/audit_log_repository.py` | Modified | +métodos de agregación y filtros |
| `app/services/auditoria_service.py` | New | Lógica de agregación |
| `app/schemas/auditoria.py` | New | DTOs read-only |
| `app/api/v1/routers/auditoria.py` | New | 4 endpoints read-only |
| `app/main.py` | Modified | Register router |
| `alembic/versions/017_auditoria.py` | New | Solo seed permiso (sin tablas) |
| `tests/test_auditoria.py` | New | Tests |

## Approaches

### Approach 1: Repo con queries de agregación directa

Agregar métodos al `AuditLogRepository`: `count_por_dia()`, `agrupar_por_docente()`, `agrupar_por_docente_materia()`, `ultimas_acciones(limit)`, `list_con_filtros()`.

**Pros**: Simple, reusa BaseRepository, mismo patrón que C-11 (analisis).
**Cons**: Muchas queries separadas, N+1 potential.
**Effort**: Medio

### Approach 2: Endpoint único con parámetros

Un solo endpoint `GET /api/auditoria/metricas?tipo=diario|docente|materia|recientes` que devuelve distintas estructuras según el tipo.

**Pros**: Menos endpoints, flexible.
**Cons**: Response model complejo (union types), difícil de documentar en OpenAPI.
**Effort**: Alto

## Recommendation

**Approach 1** — endpoints separados, queries directas. Mismo patrón que C-11 analisis. Read-only, sin modelos nuevos. 4 endpoints concretos con response models claros.

### Scope COORDINADOR

COORDINADOR con `auditoria:ver` ve SOLO sus propias acciones (`actor_id = current_user.id`). ADMIN ve todo. Scope aplicado en el service (mismo patrón que `TareaService._is_admin()`).

### Permiso

Nuevo: `auditoria:ver` para ADMIN + COORDINADOR. Sin tablas nuevas — solo seed.

## Endpoints propuestos

| Endpoint | Query | Descripción |
|----------|-------|-------------|
| `GET /api/auditoria/acciones-por-dia` | GROUP BY fecha, COUNT | Volumen diario (F9.1) |
| `GET /api/auditoria/por-docente` | GROUP BY actor_id, GROUP BY accion | Estado comunicaciones por docente (F9.1) |
| `GET /api/auditoria/recientes?limit=200` | ORDER BY fecha_hora DESC LIMIT | Últimas acciones (F9.1) |
| `GET /api/auditoria/log?fecha_desde=&fecha_hasta=&materia_id=&usuario_id=&accion=` | Filtros combinados | Log completo (F9.2) |

## Risks

- **Performance**: GROUP BY sobre tabla grande sin índices adicionales — mitigar con índices en migración
- **Scope COORDINADOR**: asegurar que la agregación por docente solo muestra datos del propio coordinador en el endpoint por-docente
- **detalle JSON**: no indexable para búsquedas — solo filtros por campos structured

## Ready for Proposal

Yes. Sin dependencias nuevas (C-05 y C-07 ya están). Sin tablas nuevas. Puro analytics read-only sobre AuditLog existente.
