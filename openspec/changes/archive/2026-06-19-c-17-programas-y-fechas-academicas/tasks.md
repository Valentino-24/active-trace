# Tasks: C-17 Programas y Fechas Academicas

## Phase 1: Models & Migration

- [x] 1.1 Create `backend/app/models/programa_materia.py` — `ProgramaMateria` with tenant-scope, soft-delete, materia_id, carrera_id, cohorte_id, titulo, referencia_archivo
- [x] 1.2 Create `backend/app/models/fecha_academica.py` — `TipoFecha` enum (Parcial|TP|Coloquio|Recuperatorio) + `FechaAcademica` with materia_id, cohorte_id, tipo, numero, periodo, fecha, titulo
- [x] 1.3 Export new models in `backend/app/models/__init__.py`
- [x] 1.4 Create `backend/alembic/versions/015_programas_fechas.py` — tables programa_materia + fecha_academica with FKs, indexes (no new permiso seed)

## Phase 2: Repositories

- [x] 2.1 Create `backend/app/repositories/programa_repository.py` — `ProgramaRepository` CRUD + list_con_filtros (materia_id, cohorte_id)
- [x] 2.2 Create `backend/app/repositories/fecha_repository.py` — `FechaRepository` CRUD + list_con_filtros (materia_id, cohorte_id, tipo, periodo)
- [x] 2.3 Export new repos in `backend/app/repositories/__init__.py`

## Phase 3: Schemas

- [x] 3.1 Create `backend/app/schemas/programas_fechas.py` — request/response DTOs for both modules, all `extra='forbid'`, responses `from_attributes=True`

## Phase 4: Services

- [x] 4.1 Create `backend/app/services/programa_fecha_service.py` — CRUD for both models, filtered listing, audit via log_action

## Phase 5: API & Wiring

- [x] 5.1 Create `backend/app/api/v1/routers/programas_fechas.py` — endpoints with guard `estructura:gestionar`:
  - Programas: POST, GET (list), PATCH /{id}, DELETE /{id}
  - Fechas: POST, GET (list with filters), PATCH /{id}, DELETE /{id}
- [x] 5.2 Modify `backend/app/main.py` — register router

## Phase 6: Testing

- [x] 6.1 Unit tests: TipoFecha enum, schema validation
- [x] 6.2 Integration: repo CRUD + filtros for both models
- [x] 6.3 Integration: service scope + audit
- [x] 6.4 E2E: HTTP endpoints, permissions (403/401), validacion (422)
- [x] 6.5 Run all tests, verify LOC ≤500 per file, `extra='forbid'` on all schemas, no business logic in routers
