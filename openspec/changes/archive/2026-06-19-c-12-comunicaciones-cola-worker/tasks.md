# Tasks: C-12 Comunicaciones — Cola y Worker

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Create `backend/app/models/comunicacion.py` — `EstadoComunicacion` enum + `Comunicacion` model with tenant-scope, soft-delete, timestamps, cifrado destinatario, FKs to Usuario/Materia
- [x] 1.2 Export `Comunicacion` in `backend/app/models/__init__.py`
- [x] 1.3 Create `backend/alembic/versions/010_crear_comunicacion.py` — table `comunicacion` with FKs, indexes; verify permissions exist in 003, do NOT reseed
- [x] 1.4 Add `smtp_host/port/user/password`, `worker_poll_interval`, `worker_batch_size` to `backend/app/core/config.py`

## Phase 2: Core Implementation

- [x] 2.1 Create `backend/app/schemas/comunicaciones.py` — `PreviewRequest/Response`, `EnviarRequest`, `ComunicacionResponse`, `LoteResponse`, `EstadisticasResponse`, `AprobarRequest`; all with `extra='forbid'`
- [x] 2.2 Create `backend/app/repositories/comunicacion_repository.py` extending `BaseRepository` — `list_pendientes(limit)`, `list_por_lote()`, `update_estado()`, `count_por_estado()`, `list_pendientes_aprobacion()`, `bulk_update_estado()`
- [x] 2.3 Export `ComunicacionRepository` in `backend/app/repositories/__init__.py`
- [x] 2.4 Create `backend/app/services/comunicacion_service.py` — pure `render_template()` (string.Template) + `validate_transition()`; service class with `preview`, `enviar`, `aprobar_lote/individual`, `cancelar_lote`, `get_estadisticas`, `get_estado_lote`; scope enforcement by role; audit via existing `log_action`
- [x] 2.5 Create `backend/app/workers/__init__.py`

## Phase 3: Integration / Wiring

- [x] 3.1 Create `backend/app/api/v1/routers/comunicaciones.py` — 8 endpoints (preview, enviar, lotes, lote detail, aprobar, cancelar, estadisticas) with `comunicacion:enviar`/`comunicacion:aprobar` guards; PROFESOR scoped by asignacion_ids
- [x] 3.2 Create `backend/app/workers/comunicacion_worker.py` — `ComunicacionWorker` with async poll loop, batch processing, string.Template render, log-only send, Pendiente→Enviando→Enviado/Error transitions
- [x] 3.3 Modify `backend/app/main.py` — import worker, start/cancel in `lifespan`, register router

## Phase 4: Testing & Verification

- [x] 4.1 Unit tests: `render_template` (all vars, unknown, empty, partial) + `validate_transition` (all valid/invalid, terminal states blocked)
- [x] 4.2 Integration: preview endpoint (valid, unknown vars, multiple recipients, no persistence); enviar (batch, same lote_id, Pendiente, audit event)
- [x] 4.3 Integration: worker cycle Pendiente→Enviando→Enviado/Error; approval flow (lote/individual approve, cancel, reject); tenant flag bypass
- [x] 4.4 Integration: permissions (401 without token, 403 without permission, 403 wrong scope); tenant isolation; cifrado (email not in responses); invalid state transitions (409)
- [x] 4.5 Run all tests, verify LOC ≤500 per file, `extra='forbid'` on all schemas, no business logic in routers
