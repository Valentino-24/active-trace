# Tasks: C-16 Tareas Internas

## Phase 1: Models & Migration

- [ ] 1.1 Create `backend/app/models/tarea.py` — `EstadoTarea` enum (Pendiente|EnProgreso|Resuelta|Cancelada) + `Tarea` model with tenant-scope, soft-delete, timestamps, materia_id (nullable), asignado_a, asignado_por, estado, descripcion, contexto_id (nullable UUID)
- [ ] 1.2 Create `backend/app/models/comentario_tarea.py` — `ComentarioTarea` model with tarea_id, autor_id, texto, creado_at, created_at (sin soft delete — trazabilidad)
- [ ] 1.3 Export new models in `backend/app/models/__init__.py`
- [ ] 1.4 Create `backend/alembic/versions/014_tareas.py` — tables tarea + comentario_tarea with FKs, indexes; seed permiso `tareas:gestionar` for TUTOR, PROFESOR, COORDINADOR, ADMIN

## Phase 2: Repositories

- [ ] 2.1 Create `backend/app/repositories/tarea_repository.py` — `TareaRepository` (CRUD, list_por_asignado con filtros, list_con_filtros admin con búsqueda libre ILIKE) + `ComentarioTareaRepository` (create, list_por_tarea ordenado ASC); all extending BaseRepository
- [ ] 2.2 Export new repos in `backend/app/repositories/__init__.py`

## Phase 3: Schemas

- [ ] 3.1 Create `backend/app/schemas/tareas.py` — `TareaCrearRequest`, `TareaEstadoUpdateRequest`, `TareaReasignarRequest`, `TareaResponse`, `TareaListResponse`, `TareaMiaResponse` (con ultimo_comentario), `ComentarioCrearRequest`, `ComentarioResponse`, `ComentarioListResponse`; all with `extra='forbid'`, responses with `from_attributes=True`

## Phase 4: Services

- [ ] 4.1 Create `backend/app/services/tarea_service.py` — `crear()`, `listar_mias()` con filtros y scope (asignado_a=current_user), `listar_admin()` con filtros combinados y búsqueda libre, `cambiar_estado()` con validación de transiciones (tabla _TRANSICIONES), `reasignar()` con audit de trazabilidad, `agregar_comentario()`, `listar_comentarios()`; audit via log_action

## Phase 5: API & Wiring

- [ ] 5.1 Create `backend/app/api/v1/routers/tareas.py` — endpoints:
  - Gestión (guard `tareas:gestionar`): POST /tareas, PATCH /tareas/{id}/estado, PATCH /tareas/{id}/asignar, POST /tareas/{id}/comentarios, GET /tareas/{id}/comentarios
  - Consulta: GET /tareas/mias (scope: propias), GET /tareas (scope: admin — todas)
- [ ] 5.2 Modify `backend/app/main.py` — register tareas router

## Phase 6: Testing

- [ ] 6.1 Unit tests: tabla de transiciones de estado (todas las combinaciones válidas e inválidas)
- [ ] 6.2 Integration: tarea repo (CRUD, list por asignado, list con filtros admin, búsqueda ILIKE); comentario repo (create, list por tarea)
- [ ] 6.3 Integration: service ciclo completo crear → mis-tareas → estado → comentar → admin; scope (usuario A no ve tareas de B en mis-tareas); transiciones válidas/inválidas
- [ ] 6.4 E2E: full HTTP flow crear → mis-tareas → estado → comentar → admin list → reasignar; permissions (403 sin tareas:gestionar, 401); validación (422, 409 transición inválida)
- [ ] 6.5 Run all tests, verify LOC ≤500 per file, `extra='forbid'` on all schemas, no business logic in routers
