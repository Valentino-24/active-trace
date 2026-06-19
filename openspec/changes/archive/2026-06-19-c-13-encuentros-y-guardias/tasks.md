# Tasks: C-13 Encuentros y Guardias

## Phase 1: Foundation / Models & Migration

- [x] 1.1 Create `backend/app/models/slot_encuentro.py` — `SlotEncuentro` model with tenant-scope, soft-delete, timestamps, FKs to Asignacion/Materia, fields: titulo, hora, dia_semana, fecha_inicio, cant_semanas, fecha_unica (nullable), meet_url, vig_desde, vig_hasta
- [x] 1.2 Create `backend/app/models/instancia_encuentro.py` — `EstadoInstancia` enum (Programado|Realizado|Cancelado) + `InstanciaEncuentro` model with tenant-scope, slot_id nullable, materia_id, fecha, hora, titulo, estado, meet_url, video_url nullable, comentario
- [x] 1.3 Create `backend/app/models/guardia.py` — `EstadoGuardia` enum (Pendiente|Realizada|Cancelada) + `Guardia` model with tenant-scope, asignacion_id, materia_id, carrera_id, cohorte_id, dia, horario, estado, comentarios, creada_at
- [x] 1.4 Export new models in `backend/app/models/__init__.py`
- [x] 1.5 Create `backend/alembic/versions/011_encuentros_guardias.py` — tables slot_encuentro, instancia_encuentro, guardia with indexes, FKs; seed permisos encuentros:gestionar and guardias:gestionar; assign to roles per matrix (PROFESOR/TUTOR/COORDINADOR/ADMIN)

## Phase 2: Repositories

- [x] 2.1 Create `backend/app/repositories/encuentro_repository.py` — `SlotEncuentroRepository` (CRUD, list_por_materia) + `InstanciaEncuentroRepository` (CRUD, list_por_slot, list_por_materia_fechas, update_estado, count_por_materia); both extending BaseRepository
- [x] 2.2 Create `backend/app/repositories/guardia_repository.py` — `GuardiaRepository` extending BaseRepository (CRUD, list_con_filtros, list_por_asignacion, export_query)
- [x] 2.3 Export new repos in `backend/app/repositories/__init__.py`

## Phase 3: Schemas

- [x] 3.1 Create `backend/app/schemas/encuentros.py` — `SlotCrearRequest` with model_validator for modo exclusivo (RN-13), `InstanciaUpdateRequest` (estado, meet_url, video_url, comentario — todos opcionales), `SlotResponse`, `InstanciaResponse`, `SlotConInstanciasResponse`, `InstanciaListResponse`, `HtmlResponse`; all with `extra='forbid'`
- [x] 3.2 Create `backend/app/schemas/guardias.py` — `GuardiaCrearRequest`, `GuardiaUpdateRequest`, `GuardiaResponse`, `GuardiaListResponse`; all with `extra='forbid'`

## Phase 4: Services

- [x] 4.1 Create `backend/app/services/encuentro_service.py` — `crear_slot()` (genera instancias síncrono), `editar_instancia()`, `listar_instancias()` con filtros y scope, `generar_html()`, `listar_slots()`, `vista_admin()`; scope enforcement by role; audit via log_action
- [x] 4.2 Create `backend/app/services/guardia_service.py` — `crear()`, `listar()` con filtros y scope, `actualizar()`, `exportar_csv()`; scope enforcement

## Phase 5: API & Wiring

- [x] 5.1 Create `backend/app/api/v1/routers/encuentros.py` — 6 endpoints (POST /slots, PATCH /instancias/{id}, GET /instancias, GET /slots, GET /instancias/{id}/html, GET /admin) with `encuentros:gestionar` guard; scope by asignacion_ids for PROFESOR/TUTOR
- [x] 5.2 Create `backend/app/api/v1/routers/guardias.py` — 4 endpoints (POST /guardias, GET /guardias, GET /guardias/export, PATCH /guardias/{id}) with `guardias:gestionar` guard; scope by asignacion_ids for PROFESOR/TUTOR
- [x] 5.3 Modify `backend/app/main.py` — register both routers

## Phase 6: Testing

- [x] 6.1 Unit tests: generación de instancias from slot recurrente (cant_semanas=0, 1, 15, casos borde), validación modos excluyentes (model_validator), HTML generation, CSV export format
- [x] 6.2 Integration: slot repository (CRUD, list por materia); instancia repository (CRUD, list con filtros, update estado); guardia repository (CRUD, list con filtros)
- [x] 6.3 Integration: crear slot recurrente genera N instancias en DB; crear fecha única genera 1; scope filter (PROFESOR ve solo su materia, COORDINADOR ve todo)
- [x] 6.4 E2E: full HTTP flow slots → instancias; full HTTP flow guardias → export; permissions (401, 403); validación 422
- [x] 6.5 Run all tests, verify LOC ≤500 per file, `extra='forbid'` on all schemas, no business logic in routers
