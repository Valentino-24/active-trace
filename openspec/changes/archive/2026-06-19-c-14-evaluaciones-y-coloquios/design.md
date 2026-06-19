# Design: C-14 Evaluaciones y Coloquios

## Context

C-13 completó encuentros y guardias (Épica 6). El siguiente hito del camino crítico son los coloquios (Épica 7): la evaluación oral que cierra el ciclo del alumno.

El flujo completo (FL-07) es:
1. COORDINADOR/PROFESOR crea convocatoria → importa alumnos habilitados
2. ALUMNO ve convocatorias disponibles → reserva turno
3. PROFESOR/COORDINADOR registra notas → consulta registro académico

Este change implementa los 3 roles (gestión, alumno, consulta/admin) en una misma API.

## Goals / Non-Goals

### Goals
- Modelo `Evaluacion` con materia, cohorte, tipo (Parcial|TP|Coloquio|Recuperatorio), instancia, días_disponibles
- Modelo `ReservaEvaluacion` con alumno_id, fecha_hora, estado Activa|Cancelada
- Modelo `ResultadoEvaluacion` con nota_final nullable (se crea al importar alumno, se completa al registrar nota)
- API de gestión: crear convocatoria, importar alumnos, cerrar, registrar notas
- API de alumno: listar disponibles, reservar turno (con control de cupo), cancelar, mis reservas
- API de consulta: métricas (F7.1), listado convocatorias (F7.4), agenda consolidada (F7.5), registro académico (F7.5)
- Permisos nuevos `coloquios:gestionar` y `coloquios:ver`
- Migración 012 con 3 tablas + seed permisos

### Non-Goals
- Integración con Moodle para importación automática de alumnos — MVP usa inserción manual por IDs
- Notificaciones push/email al alumno cuando se abre una convocatoria
- Ventana de inscripción con fecha de cierre automática (días_disponibles es informativo por ahora)
- Turnos con horario específico (franja horaria) — MVP: fecha_hora es un datetime, el alumno elige cuándo

## Decisions

### 1. Cupo: count de reservas activas

| Opción | Trade-off | Decisión |
|--------|-----------|----------|
| Count de reservas activas | Simple, siempre actualizado. Requiere query cada vez. | ✅ **Elegido** |
| Columna `cupo_restante` denormalizada | Evita count, pero puede desincronizarse. Requiere actualizar en cada reserva/cancelación. | ❌ Riesgo de inconsistencia |

El cupo disponible se calcula como `días_disponibles - count(reservas activas)`. Si es 0, se rechaza nueva reserva con 409.

```python
# En servicio:
cupo_usado = await reserva_repo.count_activas_por_evaluacion(evaluacion_id)
if cupo_usado >= evaluacion.dias_disponibles:
    raise HTTPException(409, "No hay cupo disponible")
```

### 2. Importación de alumnos: ResultadoEvaluacion como placeholder

F7.2 requiere cargar alumnos habilitados. Se implementa creando `ResultadoEvaluacion` por cada alumno con `nota_final=NULL`. Esto:
- Da visibilidad inmediata en métricas ("X alumnos convocados")
- Sirve como placeholder que el profesor completa después
- Evita una tabla separada de "alumnos habilitados"

```python
# POST /coloquios/{id}/alumnos
async def importar_alumnos(evaluacion_id, alumno_ids: list[uuid.UUID]):
    existentes = await resultado_repo.list_por_evaluacion(evaluacion_id)
    existentes_ids = {r.alumno_id for r in existentes}
    nuevos = [
        ResultadoEvaluacion(
            evaluacion_id=evaluacion_id,
            alumno_id=aid,
            nota_final=None,
        )
        for aid in alumno_ids if aid not in existentes_ids
    ]
    session.add_all(nuevos)
```

### 3. Reserva: ALUMNO se autentica como User con rol ALUMNO

El rol ALUMNO ya existe en el sistema (seed desde migration 003). El endpoint de reserva verifica que el usuario autenticado tenga rol ALUMNO en su asignación (o directamente que el token indique rol ALUMNO).

Para MVP, el alumno se autentica con JWT normal. El endpoint `POST /coloquios/{id}/reservar` usa `current_user.id` como `alumno_id` — no se acepta un `alumno_id` en el body (regla: identidad desde la sesión).

### 4. Scope: dos niveles de visibilidad

- **ALUMNO**: solo ve convocatorias donde está habilitado (existe ResultadoEvaluacion con su alumno_id) y opera sobre sus propias reservas.
- **COORDINADOR/ADMIN**: ve todo el tenant. Los endpoints de gestión requieren `coloquios:gestionar`; los de consulta requieren `coloquios:ver`.
- **PROFESOR**: según la KB (F7.1–F7.5), las acciones de gestión las hace COORDINADOR. PROFESOR puede crear convocatorias (HU-31 dice "Como PROFESOR") e importar alumnos. Se le asigna `coloquios:gestionar` pero scoped a sus materias.

### 5. Panel de métricas (F7.1): consultas agregadas

`GET /api/coloquios/metricas` devuelve:
```json
{
  "total_alumnos_cargados": 150,
  "instancias_activas": 5,
  "reservas_activas": 42,
  "notas_registradas": 80
}
```

Se implementa con consultas SQLAlchemy agregadas (count, group by). Es solo COORDINADOR/ADMIN (no tiene scope de materia).

### 6. Permisos: coloquios:gestionar y coloquios:ver

| Permiso | PROFESOR | COORDINADOR | ADMIN |
|---------|----------|-------------|-------|
| `coloquios:gestionar` | ✅ (scope materia) | ✅ | ✅ |
| `coloquios:ver` | ✅ (scope materia) | ✅ | ✅ |

ALUMNO no necesita estos permisos — los endpoints de alumno usan un guard diferente que verifica rol ALUMNO.

### 7. Migración 012: 3 tablas + seed permisos

Sigue el mismo patrón que migration 011 (uuid5 deterministic IDs, check exist antes de insert).

## Data Flow

```
COORDINADOR                      SERVICE                           DB
    │                                │                             │
    ├─ POST /coloquios ──────────────┤                             │
    │  {materia, cohorte, tipo,      │                             │
    │   instancia, dias} ────────────┼────────────────────────────►│ INSERT evaluacion
    │  ◄── evaluacion ───────────────┤                             │
    │                                │                             │
    ├─ POST /coloquios/{id}/alumnos ─┤                             │
    │  [alumno_id1, alumno_id2] ─────┼────────────────────────────►│ INSERT resultado_evaluacion
    │  ◄── N alumnos importados ─────┤                             │   (nota_final=NULL)
    │                                │                             │
    │  [después del coloquio]        │                             │
    ├─ PATCH /coloquios/resultados/{id} ─┤                         │
    │  {nota_final: "8"} ─────────────┼────────────────────────────►│ UPDATE resultado_evaluacion
    │                                │                             │

ALUMNO                            SERVICE                           DB
    │                                │                             │
    ├─ GET /coloquios/disponibles ───┤                             │
    │  ◄── convocatorias activas ─────┤                             │
    │                                │                             │
    ├─ POST /coloquios/{id}/reservar ─┤                             │
    │  {fecha_hora: "2026-07-15T10:00"} ──► count reservas activas │
    │                                │  if cupo < dias_disponibles: │
    │                                ├────────────────────────────►│ INSERT reserva_evaluacion
    │  ◄── reserva creada ───────────┤                             │
    │                                │                             │
    ├─ DELETE /coloquios/reservas/{id} ─┤                          │
    │                                ├────────────────────────────►│ UPDATE estado=Cancelada
    │  ◄── reserva cancelada ────────┤                             │

COORDINADOR                      SERVICE                           DB
    │                                │                             │
    ├─ GET /coloquios/metricas ──────┤                             │
    │                                ├──► SELECT count(*) FROM ... │
    │  ◄── {totales} ────────────────┤                             │
    │                                │                             │
    ├─ GET /coloquios/agenda ────────┤                             │
    │  ◄── reservas activas ─────────┤                             │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/evaluacion.py` | Create | Modelo `Evaluacion` — convocatoria de coloquio |
| `backend/app/models/reserva_evaluacion.py` | Create | Modelo `ReservaEvaluacion` — turno reservado |
| `backend/app/models/resultado_evaluacion.py` | Create | Modelo `ResultadoEvaluacion` — nota final |
| `backend/app/models/__init__.py` | Modify | Export nuevos modelos |
| `backend/app/repositories/coloquio_repository.py` | Create | EvaluacionRepository + ReservaEvaluacionRepository + ResultadoEvaluacionRepository |
| `backend/app/repositories/__init__.py` | Modify | Export nuevos repos |
| `backend/app/schemas/coloquios.py` | Create | DTOs: crear, importar, reservar, métricas, agenda, registro |
| `backend/app/services/coloquio_service.py` | Create | Lógica de convocatorias, importación, reservas, notas, métricas |
| `backend/app/api/v1/routers/coloquios.py` | Create | Endpoints /api/coloquios/* con guards |
| `backend/app/api/v1/routers/__init__.py` | Modify | Export router |
| `backend/app/main.py` | Modify | Register router |
| `backend/alembic/versions/012_coloquios.py` | Create | Tablas evaluacion, reserva_evaluacion, resultado_evaluacion + seed permisos |

## Interfaces / Contracts

### Router: `POST /api/coloquios` (F7.3 — guard: `coloquios:gestionar`)

```json
// Request
{
  "materia_id": "uuid",
  "cohorte_id": "uuid",
  "tipo": "Coloquio",
  "instancia": "Coloquio Final 2026",
  "dias_disponibles": 30
}
// Response
{
  "id": "uuid",
  "materia_id": "uuid",
  "cohorte_id": "uuid",
  "tipo": "Coloquio",
  "instancia": "Coloquio Final 2026",
  "dias_disponibles": 30,
  "activa": true,
  "created_at": "..."
}
```

### Router: `POST /api/coloquios/{id}/alumnos` (F7.2 — guard: `coloquios:gestionar`)

```json
// Request
{
  "alumno_ids": ["uuid1", "uuid2", "uuid3"]
}
// Response
{
  "importados": 3,
  "ya_existentes": 0
}
```

### Router: `GET /api/coloquios` (F7.4 — guard: `coloquios:ver`)

```json
// Response
{
  "items": [
    {
      "id": "uuid",
      "materia": "Programación I",
      "instancia": "Coloquio Final",
      "convocados": 50,
      "reservas_activas": 30,
      "cupo_disponible": 20,
      "activa": true
    }
  ],
  "total": 5
}
```

### Router: `POST /api/coloquios/{id}/reservar` (ALUMNO — guard: rol ALUMNO)

```json
// Request
{
  "fecha_hora": "2026-07-15T10:00:00Z"
}
// Response 201
{
  "id": "uuid",
  "evaluacion_id": "uuid",
  "fecha_hora": "2026-07-15T10:00:00Z",
  "estado": "Activa"
}
// Response 409 — sin cupo
{
  "detail": "No hay cupo disponible para esta convocatoria"
}
```

### Router: `GET /api/coloquios/metricas` (F7.1 — guard: `coloquios:ver`)

```json
{
  "total_alumnos_cargados": 150,
  "instancias_activas": 5,
  "reservas_activas": 42,
  "notas_registradas": 80
}
```

### Router: `GET /api/coloquios/disponibles` (ALUMNO)

```json
{
  "items": [
    {
      "id": "uuid",
      "materia": "Programación I",
      "instancia": "Coloquio Final",
      "dias_disponibles": 30,
      "tiene_reserva": false
    }
  ]
}
```

### Router: `GET /api/coloquios/agenda` (F7.5 — guard: `coloquios:ver`)

```json
{
  "items": [
    {
      "id": "uuid",
      "alumno": "Juan Pérez",
      "materia": "Programación I",
      "fecha_hora": "2026-07-15T10:00",
      "evaluacion": "Coloquio Final",
      "estado": "Activa"
    }
  ]
}
```

### Router: `GET /api/coloquios/registro` (F7.5 — guard: `coloquios:ver`)

```json
{
  "items": [
    {
      "alumno": "Juan Pérez",
      "materia": "Programación I",
      "instancia": "Coloquio Final",
      "nota_final": "8",
      "registrada_at": "..."
    }
  ]
}
```

### Router: `PATCH /api/coloquios/resultados/{id}` (guard: `coloquios:gestionar`)

```json
// Request
{
  "nota_final": "8"
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Validación de schemas (tipo enum, campos requeridos) | Test functions directly |
| Integration | Evaluacion repo: CRUD, list activas | seed_data fixture |
| Integration | Reserva repo: CRUD, count_activas_por_evaluacion, list_por_alumno | seed_data fixture |
| Integration | Resultado repo: CRUD, list_por_evaluacion, count_notas_registradas | seed_data fixture |
| Integration | Service: importar alumnos crea resultados, duplicados se saltan | seed_data fixture |
| Integration | Service: reservar con cupo disponible → éxito; sin cupo → 409 | seed_data fixture |
| Integration | Service: cancelar reserva libera cupo | seed_data fixture |
| Integration | Alumno ve solo convocatorias donde está habilitado | Test with alumno fixture |
| E2E | Full HTTP flow: crear → importar → alumno reserva → profesor nota | httpx AsyncClient |
| E2E | Permissions: 403 sin token/permiso, 401 | Test guards |
| E2E | Métricas reflejan datos insertados | httpx AsyncClient |

**Seed data needed**: tenant, materia, cohorte, users (profesor, coordinador, 3 alumnos), asignaciones para cada rol, permissions coloquios:gestionar y coloquios:ver.

## Migration / Rollout

**Migration 012** (`012_coloquios.py`):
- `down_revision = "011"`
- `create_table("evaluacion")`: id, tenant_id, materia_id, cohorte_id, tipo (varchar), instancia, dias_disponibles, activa (bool default true), timestamps, deleted_at
- `create_table("reserva_evaluacion")`: id, tenant_id, evaluacion_id, alumno_id, fecha_hora, estado (varchar default 'Activa'), timestamps
- `create_table("resultado_evaluacion")`: id, tenant_id, evaluacion_id, alumno_id, nota_final (nullable), registrada_at (nullable), timestamps
- Índices: ix_reserva_evaluacion (evaluacion_id), ix_reserva_alumno (alumno_id), ix_resultado_evaluacion (evaluacion_id)
- FK: todas con CASCADE
- Seed permisos: `coloquios:gestionar` y `coloquios:ver` en permission + role_permission

**Rollout:**
1. Deploy migration 012
2. Deploy código
3. Verificar registro en main.py

## Open Questions

- [ ] **¿El ALUMNO se autentica con JWT normal?** Sí — MVP. No hay auth separada para alumnos. El rol ALUMNO ya existe en el seed.
- [ ] **Días disponibles = cupo máximo?** Sí. Cada día_disponible = 1 cupo. Si dias_disponibles=30, máximo 30 reservas activas. Si se requiere cupo > 1 por día, se ajusta en change futuro.
- [ ] **¿Nota final texto o numérico?** Texto (puede ser "8", "Aprobado", "Sobresaliente"). El schema acepta string.
