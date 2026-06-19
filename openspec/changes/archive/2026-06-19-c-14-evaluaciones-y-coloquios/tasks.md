# Tasks: C-14 Evaluaciones y Coloquios

## Phase 1: Models & Migration

- [x] 1.1 Create `backend/app/models/evaluacion.py` — `TipoEvaluacion` enum (Parcial|TP|Coloquio|Recuperatorio) + `Evaluacion` model with tenant-scope, materia_id, cohorte_id, tipo, instancia, dias_disponibles, activa flag, timestamps, soft-delete
- [x] 1.2 Create `backend/app/models/reserva_evaluacion.py` — `EstadoReserva` enum (Activa|Cancelada) + `ReservaEvaluacion` model with tenant-scope, evaluacion_id, alumno_id, fecha_hora, estado, timestamps
- [x] 1.3 Create `backend/app/models/resultado_evaluacion.py` — `ResultadoEvaluacion` model with tenant-scope, evaluacion_id, alumno_id, nota_final (nullable), registrada_at (nullable), timestamps
- [x] 1.4 Export new models in `backend/app/models/__init__.py`
- [x] 1.5 Create `backend/alembic/versions/012_coloquios.py` — tables evaluacion, reserva_evaluacion, resultado_evaluacion with indexes, FKs; seed permisos coloquios:gestionar and coloquios:ver; assign to roles

## Phase 2: Repositories

- [x] 2.1 Create `backend/app/repositories/coloquio_repository.py` — `EvaluacionRepository` (CRUD, list_activas, list_con_metricas, update), `ReservaEvaluacionRepository` (CRUD, count_activas_por_evaluacion, list_por_alumno, list_activas), `ResultadoEvaluacionRepository` (CRUD, list_por_evaluacion, count_notas_registradas, list_con_notas); all extending BaseRepository
- [x] 2.2 Export new repos in `backend/app/repositories/__init__.py`

## Phase 3: Schemas

- [x] 3.1 Create `backend/app/schemas/coloquios.py` — `EvaluacionCrearRequest`, `EvaluacionUpdateRequest`, `EvaluacionResponse`, `ImportarAlumnosRequest`, `ImportarAlumnosResponse`, `ReservaRequest`, `ReservaResponse`, `ResultadoUpdateRequest`, `ResultadoResponse`, `MetricasResponse`, `AgendaResponse`, `RegistroResponse`, `ConvocatoriaDisponibleResponse`, `MisReservasResponse`; all with `extra='forbid'`, responses with `from_attributes=True`

## Phase 4: Services

- [x] 4.1 Create `backend/app/services/coloquio_service.py` — `crear_convocatoria()`, `importar_alumnos()`, `listar_convocatorias()` con métricas derivadas, `cerrar_convocatoria()`, `reservar_turno()` con control de cupo, `cancelar_reserva()`, `listar_disponibles_para_alumno()`, `listar_mis_reservas()`, `registrar_nota()`, `get_metricas()`, `get_agenda()`, `get_registro()`; scope enforcement; audit via log_action

## Phase 5: API & Wiring

- [x] 5.1 Create `backend/app/api/v1/routers/coloquios.py` — endpoints:
  - Gestión (guard `coloquios:gestionar`): POST /coloquios, POST /coloquios/{id}/alumnos, PATCH /coloquios/{id}, PATCH /coloquios/resultados/{id}
  - Consulta (guard `coloquios:ver`): GET /coloquios, GET /coloquios/metricas, GET /coloquios/agenda, GET /coloquios/registro
  - Alumno (guard rol ALUMNO): GET /coloquios/disponibles, POST /coloquios/{id}/reservar, GET /coloquios/mis-reservas, DELETE /coloquios/reservas/{id}
- [x] 5.2 Modify `backend/app/main.py` — register coloquios router

## Phase 6: Testing

- [x] 6.1 Unit tests: schema validation (tipo enum, campos requeridos, importación con lista vacía)
- [x] 6.2 Integration: evaluacion repo (CRUD, list activas, list con métricas); reserva repo (CRUD, count_activas, list por alumno, list activas); resultado repo (CRUD, count_notas, list con notas)
- [x] 6.3 Integration: service crear convocatoria → importar alumnos → reservar con cupo → 409 sin cupo → cancelar reserva → registrar nota; alumno ve solo sus convocatorias
- [x] 6.4 E2E: full flow crear → importar → alumno reserva → profesor nota → métricas; permissions (401, 403 para gestión, 403 para alumno en endpoints de gestión)
- [x] 6.5 Run all tests, verify LOC ≤500 per file, `extra='forbid'` on all schemas, no business logic in routers
