## Why

El sistema ya cubre encuentros, coloquios, guardias y comunicaciones. Pero la coordinación interna del equipo docente (asignar tareas, dar seguimiento, comentar) queda fuera del sistema. Eso es el módulo de tareas internas (Épica 8, F8.1–F8.3).

Sin este change, la coordinación usa canales informales (WhatsApp, mail) sin trazabilidad. Es un módulo de alto uso: cientos de tareas simultáneas durante el período activo.

Depende de C-07 (asignaciones) porque las tareas se asignan a docentes según su asignación en el tenant.

## What Changes

Nuevo módulo `tareas` con ciclo completo: asignación, transición de estados, comentarios en hilo, administración global.

### Modelos
- **`Tarea`**: asignado_a, asignado_por, materia_id (nullable), estado (Pendiente|EnProgreso|Resuelta|Cancelada), descripcion, contexto_id (nullable).
- **`ComentarioTarea`**: tarea_id, autor_id, texto, creado_at.

### Funcionalidades

- **F8.1 — Mis tareas** (TUTOR, PROFESOR, COORDINADOR):
  - `GET /api/tareas/mias` — tareas donde `asignado_a = current_user`. Filtros: materia, estado. Incluye último comentario.

- **F8.2 — Asignar/Delegar tarea** (PROFESOR, COORDINADOR, guard `tareas:gestionar`):
  - `POST /api/tareas` — crear tarea. Asigna a un docente (asignado_a), guarda quién asigna (asignado_por).
  - `PATCH /api/tareas/{id}/asignar` — reasignar a otro docente (delegación). Trazabilidad: queda registro de quién reasignó.

- **F8.3 — Admin global** (COORDINADOR, ADMIN, guard `tareas:gestionar`):
  - `GET /api/tareas` — todas las tareas del tenant. Filtros: asignado_a, asignado_por, materia, estado, búsqueda libre.
  - `PATCH /api/tareas/{id}/estado` — cambiar estado.
  - `POST /api/tareas/{id}/comentarios` — agregar comentario al hilo.
  - `GET /api/tareas/{id}/comentarios` — listar comentarios de una tarea.

### Scope
- **TUTOR/PROFESOR**: ve solo tareas donde `asignado_a = current_user` (F8.1). Puede crear tareas (F8.2) y cambiar estado de las propias.
- **COORDINADOR/ADMIN**: ve todas las tareas del tenant (F8.3). Puede crear, reasignar, cambiar estado, comentar en cualquier tarea.

### Transversal
- **Permiso**: `tareas:gestionar` (nuevo). Se seedea en migration.
- **Migración 014**: tablas `tarea`, `comentario_tarea`.
- **Audit**: acciones `TAREA_CREAR`, `TAREA_REASIGNAR`, `TAREA_CAMBIAR_ESTADO`, `TAREA_COMENTAR`.

## Capabilities

### New Capabilities
- `tareas`: Workflow de tareas internas — asignación, delegación con trazabilidad, transiciones de estado, comentarios en hilo, administración global con filtros.

### Modified Capabilities
None.

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/tarea.py` | New | Modelo `Tarea` + enum EstadoTarea |
| `backend/app/models/comentario_tarea.py` | New | Modelo `ComentarioTarea` |
| `backend/app/repositories/tarea_repository.py` | New | TareaRepository + ComentarioTareaRepository |
| `backend/app/schemas/tareas.py` | New | Pydantic DTOs |
| `backend/app/services/tarea_service.py` | New | Lógica: CRUD, transiciones, comentarios, scope |
| `backend/app/api/v1/routers/tareas.py` | New | Endpoints /api/tareas/* |
| `backend/app/main.py` | Modified | Register router |
| `backend/alembic/versions/014_tareas.py` | New | Migration: tarea + comentario_tarea + seed permiso |
