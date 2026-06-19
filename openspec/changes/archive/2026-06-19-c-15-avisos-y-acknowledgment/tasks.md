# Tasks: C-15 Avisos y Acknowledgment

## Phase 1: Models & Migration

- [x] 1.1 Create `backend/app/models/aviso.py` — enums `AlcanceAviso` (Global|PorMateria|PorCohorte|PorRol), `SeveridadAviso` (Info|Advertencia|Crítico) + `Aviso` model with tenant-scope, soft-delete, timestamps, alcance, materia_id (nullable), cohorte_id (nullable), rol_destino (nullable), severidad, titulo, cuerpo, inicio_en, fin_en, orden, activo, requiere_ack
- [x] 1.2 Create `backend/app/models/acknowledgment_aviso.py` — `AcknowledgmentAviso` model with aviso_id, usuario_id, confirmado_at, created_at (NO soft delete — registro de auditoría)
- [x] 1.3 Export new models in `backend/app/models/__init__.py`
- [x] 1.4 Create `backend/alembic/versions/013_avisos.py` — tables aviso + acknowledgment_aviso with FK, indexes; seed permiso `avisos:publicar` for COORDINADOR and ADMIN

## Phase 2: Repositories

- [x] 2.1 Create `backend/app/repositories/aviso_repository.py` — `AvisoRepository` (CRUD, list_activos_para_usuario con filtros combinados de alcance/vigencia/rol, list_con_contadores) + `AcknowledgmentRepository` (create, count_por_aviso, list_por_aviso, exists_por_usuario); all extending BaseRepository
- [x] 2.2 Export new repos in `backend/app/repositories/__init__.py`

## Phase 3: Schemas

- [x] 3.1 Create `backend/app/schemas/avisos.py` — `AvisoCrearRequest`, `AvisoUpdateRequest`, `AvisoResponse`, `AvisoListResponse`, `MisAvisosResponse`, `AckResponse`, `AcksListResponse`; all with `extra='forbid'`, responses with `from_attributes=True`

## Phase 4: Services

- [x] 4.1 Create `backend/app/services/aviso_service.py` — `crear()`, `actualizar()`, `eliminar()`, `listar_gestion()` con contadores, `listar_mis_avisos()` con filtrado por alcance/rol/cohorte/materia/vigencia/ack (RN-18/20), `ack()` con validación (solo si requiere_ack, no duplicado), `listar_acks()`; audit via log_action; orden por `orden` ASC, `created_at` DESC

## Phase 5: API & Wiring

- [x] 5.1 Create `backend/app/api/v1/routers/avisos.py` — endpoints:
  - Gestión (guard `avisos:publicar`): POST /avisos, PATCH /avisos/{id}, DELETE /avisos/{id}, GET /avisos, GET /avisos/{id}/acks
  - Usuario (sin permiso especial): GET /avisos/mis-avisos, POST /avisos/{id}/ack
- [x] 5.2 Modify `backend/app/main.py` — register avisos router

## Phase 6: Testing

- [x] 6.1 Unit tests: filtrado por alcance (Global, PorMateria, PorRol, PorCohorte), ventana de vigencia (antes/dentro/después), ordenamiento por orden ASC
- [x] 6.2 Integration: aviso repo (CRUD, list_activos_para_usuario con combinaciones de filtros); acknowledgment repo (create, count, exists)
- [x] 6.3 Integration: service crear aviso → visible para usuario correcto → ack → oculto; 409 ack duplicado; 409 ack sin requiere_ack
- [x] 6.4 E2E: full HTTP flow crear → listar gestión → mis-avisos → ack → mis-avisos (oculto) → listar acuses; permissions (403 sin avisos:publicar, 200 en mis-avisos/ack sin permiso)
- [x] 6.5 Run all tests, verify LOC ≤500 per file, `extra='forbid'` on all schemas, no business logic in routers
