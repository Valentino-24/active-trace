# Design: C-16 Tareas Internas

## Context

El sistema cubre encuentros, coloquios, guardias y comunicaciones. Pero la coordinación del equipo docente (asignar tareas, seguimiento, comentarios) queda fuera. Este change implementa Épica 8 (F8.1–F8.3), módulo de alto uso con cientos de tareas simultáneas.

Depende de C-07 porque las tareas se asignan a usuarios con asignaciones activas.

## Goals / Non-Goals

### Goals
- Modelo `Tarea` con FK a usuario asignado/asignador, materia (nullable), estado, descripción, contexto_id (nullable)
- Modelo `ComentarioTarea` con tarea_id, autor_id, texto, creado_at
- API: crear tarea, listar mis tareas, listar admin global, reasignar (trazabilidad), cambiar estado, comentar en hilo
- Scope: usuario ve solo sus tareas; coordinador/admin ve todas
- Permiso nuevo `tareas:gestionar`
- Migración 014 con 2 tablas + seed permiso

### Non-Goals
- Notificaciones push al asignar tarea (lo cubre C-12 si se integra)
- Adjuntos/archivos en comentarios (MVP solo texto)
- Tareas recurrentes o templates
- Prioridades (el estado cubre el seguimiento)

## Decisions

### 1. Estados de tarea: Pendiente → EnProgreso → Resuelta → Cancelada

FL-05 menciona estados "Abierta", "en progreso", "completada". La KB E12 define: Pendiente | En progreso | Resuelta | Cancelada. Se usa esta última.

Transiciones permitidas:
- Pendiente → EnProgreso, Cancelada
- EnProgreso → Resuelta, Cancelada
- Resuelta, Cancelada: terminales (no se reabren en MVP)

La validación se implementa en el servicio.

```python
_TRANSICIONES = {
    EstadoTarea.Pendiente: {EstadoTarea.EnProgreso, EstadoTarea.Cancelada},
    EstadoTarea.EnProgreso: {EstadoTarea.Resuelta, EstadoTarea.Cancelada},
    EstadoTarea.Resuelta: set(),      # terminal
    EstadoTarea.Cancelada: set(),     # terminal
}
```

### 2. Scope: dos niveles

- **TUTOR/PROFESOR** (`GET /api/tareas/mias`): solo ve tareas donde `asignado_a = current_user.id`. Puede cambiar estado de sus propias tareas.
- **COORDINADOR/ADMIN** (`GET /api/tareas`): ve todas las tareas del tenant. Puede operar sobre cualquier tarea.

Scope: COORDINADOR/ADMIN tiene permiso `tareas:gestionar` y acceso global. TUTOR/PROFESOR también tiene el permiso pero su alcance está limitado por `asignado_a == current_user`.

### 3. Permiso único: `tareas:gestionar`

Un solo permiso para todas las acciones. El scope (propia vs todas) se define por rol:

| Acción | TUTOR/PROFESOR | COORDINADOR/ADMIN |
|--------|---------------|-------------------|
| Ver mis tareas | ✅ (propias) | ✅ (propias) |
| Ver admin global | ❌ | ✅ |
| Crear tarea | ✅ (asigna a otros) | ✅ |
| Reasignar | ✅ (propias) | ✅ (cualquiera) |
| Cambiar estado | ✅ (propias) | ✅ (cualquiera) |
| Comentar | ✅ (propias) | ✅ (cualquiera) |

### 4. Comentarios: hilo cronológico

Los comentarios se almacenan en `comentario_tarea` con `creado_at` timestamp. Se listan ASC por fecha. No hay edición ni eliminación de comentarios (trazabilidad).

### 5. Delegación con trazabilidad

Al reasignar (`PATCH /api/tareas/{id}/asignar`), se cambia `asignado_a` y se registra audit `TAREA_REASIGNAR` con el usuario anterior y el nuevo. No se guarda historial de asignaciones previas (el audit log sirve como trazabilidad).

```python
async def reasignar(tarea_id, nuevo_asignado_id):
    tarea = await tarea_repo.get(tarea_id)
    viejo = tarea.asignado_a
    tarea.asignado_a = nuevo_asignado_id
    await log_action("TAREA_REASIGNAR", {...})
```

### 6. Búsqueda libre (F8.3)

El endpoint admin `GET /api/tareas` soporta filtros: `asignado_a`, `asignado_por`, `materia_id`, `estado`, y `q` para búsqueda libre sobre `descripcion` (ILIKE).

## Data Flow

```
PROFESOR                         SERVICE                           DB
    │                                │                             │
    ├─ POST /tareas ─────────────────┤                             │
    │  {asignado_a, materia_id,      │                             │
    │   descripcion} ────────────────┼────────────────────────────►│ INSERT tarea
    │  ◄── tarea Pendiente ─────────┤                           │ (estado=Pendiente)
    │                                │                             │
    │  [docente trabaja en la tarea] │                             │
    ├─ PATCH /tareas/{id}/estado ────┤                             │
    │  {estado: "EnProgreso"} ───────┼────────────────────────────►│ UPDATE estado
    │  ◄── tarea actualizada ────────┤                             │
    │                                │                             │
    ├─ POST /tareas/{id}/comentarios ┤                             │
    │  {texto: "Avancé con..."} ─────┼────────────────────────────►│ INSERT comentario
    │                                │                             │

COORDINADOR                      SERVICE                           DB
    │                                │                             │
    ├─ GET /tareas ──────────────────┤                             │
    │  ?estado=Pendiente&materia=X ──┼────────────────────────────►│ SELECT tareas
    │  ◄── [tareas] ─────────────────┤                           │ (filtrado)
    │                                │                             │
    ├─ PATCH /tareas/{id}/estado ────┤                             │
    │  {estado: "Resuelta"} ─────────┼────────────────────────────►│ UPDATE
    │  ◄── tarea cerrada ───────────┤                             │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/tarea.py` | Create | Modelo `Tarea` + `EstadoTarea` enum |
| `backend/app/models/comentario_tarea.py` | Create | Modelo `ComentarioTarea` |
| `backend/app/models/__init__.py` | Modify | Export nuevos modelos |
| `backend/app/repositories/tarea_repository.py` | Create | TareaRepository + ComentarioTareaRepository |
| `backend/app/repositories/__init__.py` | Modify | Export nuevos repos |
| `backend/app/schemas/tareas.py` | Create | DTOs request/response |
| `backend/app/services/tarea_service.py` | Create | Lógica: CRUD, transiciones, comentarios, scope |
| `backend/app/api/v1/routers/tareas.py` | Create | Endpoints /api/tareas/* |
| `backend/app/main.py` | Modify | Register router |
| `backend/alembic/versions/014_tareas.py` | Create | Tablas tarea + comentario_tarea + seed permiso |

## Interfaces / Contracts

### Router: `POST /api/tareas` (F8.2 — guard: `tareas:gestionar`)

```json
// Request
{
  "asignado_a": "uuid",
  "materia_id": "uuid",
  "descripcion": "Preparar informe de atrasados de Programación I"
}
// Response 201
{ "id": "uuid", "estado": "Pendiente", "asignado_por": "uuid (current_user)", ... }
```

### Router: `GET /api/tareas/mias` (F8.1 — guard: `tareas:gestionar`, scope: propias)

```json
// Query: ?estado=Pendiente&materia_id=uuid
{
  "items": [
    {
      "id": "uuid",
      "descripcion": "...",
      "estado": "Pendiente",
      "materia_id": "uuid",
      "asignado_por": "uuid",
      "ultimo_comentario": "Avancé con...",
      "created_at": "..."
    }
  ],
  "total": 5
}
```

### Router: `GET /api/tareas` (F8.3 — guard: `tareas:gestionar`, admin global)

```json
// Query: ?asignado_a=uuid&asignado_por=uuid&materia_id=uuid&estado=Pendiente&q=informe
{
  "items": [
    {
      "id": "uuid",
      "asignado_a": "uuid",
      "asignado_por": "uuid",
      "materia_id": "uuid",
      "descripcion": "Preparar informe...",
      "estado": "Pendiente",
      "created_at": "..."
    }
  ],
  "total": 20
}
```

### Router: `PATCH /api/tareas/{id}/estado` (guard: `tareas:gestionar`)

```json
// Request
{ "estado": "EnProgreso" }
// Response 200
{ "id": "uuid", "estado": "EnProgreso", ... }
// Response 409 — transición inválida
{ "detail": "Transición inválida: Resuelta → Pendiente" }
```

### Router: `PATCH /api/tareas/{id}/asignar` (F8.2 — guard: `tareas:gestionar`)

```json
// Request
{ "asignado_a": "nuevo-uuid" }
```

### Router: `POST /api/tareas/{id}/comentarios` (guard: `tareas:gestionar`)

```json
// Request
{ "texto": "Avancé con la revisión del TP2. Queda pendiente la carga de notas." }
// Response 201
{ "id": "uuid", "autor_id": "uuid", "texto": "...", "creado_at": "..." }
```

### Router: `GET /api/tareas/{id}/comentarios` (guard: `tareas:gestionar`)

```json
{
  "items": [
    { "id": "uuid", "autor_id": "uuid", "texto": "...", "creado_at": "..." }
  ],
  "total": 3
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Transiciones de estado válidas e inválidas (tabla de decisiones) | Test pure function |
| Integration | Tarea repo: CRUD, list_por_asignado, list_con_filtros, búsqueda libre | seed_data fixture |
| Integration | Comentario repo: create, list_por_tarea | seed_data fixture |
| Integration | Service: crear tarea → asignado ve en mis-tareas → cambia estado → comenta → coordinador ve en admin | seed_data fixture |
| Integration | Scope: usuario A no ve tareas de usuario B en mis-tareas | seed_data fixture |
| E2E | Full HTTP flow: crear → mis-tareas → estado → comentar → admin list → reasignar | httpx AsyncClient |
| E2E | Permissions: 403 sin `tareas:gestionar`, 401 sin token | Test guards |
| E2E | Validación: 422 sin campos, 409 transición inválida | Test edge cases |

## Migration / Rollout

**Migration 014** (`014_tareas.py`):
- `down_revision = "013"`
- `create_table("tarea")`: id, tenant_id, materia_id (nullable), asignado_a, asignado_por, estado (varchar), descripcion, contexto_id (nullable UUID), timestamps, deleted_at
- `create_table("comentario_tarea")`: id, tenant_id, tarea_id, autor_id, texto (text), creado_at (datetime), created_at (sin deleted_at — trazabilidad)
- FK: tarea → tenant, materia, users (asignado_a, asignado_por); comentario → tenant, tarea, users
- Índices: ix_tarea_asignado (tenant_id, asignado_a, deleted_at), ix_tarea_estado (tenant_id, estado), ix_comentario_tarea (tarea_id)
- Seed: permiso `tareas:gestionar` para TUTOR, PROFESOR, COORDINADOR, ADMIN

## Open Questions

- [ ] **Contexto_id**: ¿qué entidades del dominio puede referenciar? Por ahora queda como UUID libre, sin FK. El frontend resuelve el tipo según el módulo.
- [ ] **¿Puede un TUTOR crear tareas?** Según F8.2 solo PROFESOR/COORDINADOR. Pero la matriz de permisos podría extenderlo. MVP: solo PROFESOR y COORDINADOR tienen el permiso.
