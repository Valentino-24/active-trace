# Tasks: C-19 Panel de Auditoria y Metricas

## Phase 1: Repository

- [x] 1.1 Extend `backend/app/repositories/audit_log_repository.py` — add `acciones_por_dia()`, `metricas_por_docente()`, `recientes(limit)`, `list_con_filtros()`

## Phase 2: Schemas

- [x] 2.1 Create `backend/app/schemas/auditoria.py` — DTOs for 4 endpoints, `extra='forbid'`

## Phase 3: Service

- [x] 3.1 Create `backend/app/services/auditoria_service.py` — scope logic (ADMIN vs COORDINADOR), call repo methods

## Phase 4: API & Migration

- [x] 4.1 Create `backend/app/api/v1/routers/auditoria.py` — 4 endpoints with guard `auditoria:ver`
- [x] 4.2 Modify `backend/app/main.py` — register router
- [x] 4.3 Create `backend/alembic/versions/017_auditoria.py` — CREATE INDEX + seed `auditoria:ver`

## Phase 5: Testing

- [x] 5.1 Unit tests: scope logic
- [x] 5.2 Integration: repo aggregation queries
- [x] 5.3 E2E: endpoints, filtros, permisos (403/401), scope COORDINADOR
- [x] 5.4 Run all tests, verify LOC ≤500
