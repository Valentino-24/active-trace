# Design: C-19 Panel de Auditoria y Metricas

## Context

ALTO governance. Read-only analytics sobre AuditLog (C-05). Sin modelos ni tablas nuevas.

## Decisions

### 1. Queries directas sin ORM complejo

GROUP BY y agregaciones via `func.count()`, `func.date()`. Mismo patron que `AnalisisRepository` en C-11.

### 2. Scope COORDINADOR

`_is_admin()` check (mismo patron C-16). ADMIN ve todo, COORDINADOR filtrado por `actor_id == current_user.id`.

### 3. Permiso `auditoria:ver`

ADMIN + COORDINADOR. Solo seed en migracion.

### 4. Indice para GROUP BY

`CREATE INDEX ix_audit_log_fecha ON audit_log(tenant_id, fecha_hora)` para acelerar `GROUP BY DATE(fecha_hora)`.

## Endpoints

| Endpoint | F9 | Query |
|----------|-----|-------|
| `GET /api/auditoria/acciones-por-dia?desde=&hasta=` | F9.1 | `GROUP BY DATE(fecha_hora)` → count |
| `GET /api/auditoria/por-docente?desde=&hasta=` | F9.1 | `GROUP BY actor_id, accion` → count + ultima |
| `GET /api/auditoria/recientes?limit=200` | F9.1 | `ORDER BY fecha_hora DESC LIMIT` |
| `GET /api/auditoria/log?fecha_desde=&fecha_hasta=&materia_id=&usuario_id=&accion=` | F9.2 | Filtros AND |

## Migration 017

Solo `CREATE INDEX` + seed `auditoria:ver`. Sin tablas nuevas.

## Testing

| Layer | What | Approach |
|-------|------|----------|
| Unit | Scope COORDINADOR vs ADMIN | Pure function |
| Integration | Repo queries de agregacion | seed_data con audit_log entries |
| E2E | Endpoints + filtros + permisos | httpx |
