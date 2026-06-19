# Design: C-13 Encuentros y Guardias

## Context

C-07 modeló el equipo docente (asignaciones, roles). C-10/C-11 completaron calificaciones y análisis. C-12 cerró comunicaciones. El sistema ya importa, analiza y comunica, pero no cubre la operación diaria del docente: planificar encuentros sincrónicos, registrar su realización, publicar grabaciones, y llevar registro de guardias de atención.

Este change implementa la Épica 6 completa (F6.1–F6.6). Es dependencia de C-14 (coloquios) y C-22 (frontend docente).

Los permisos `encuentros:gestionar` y `guardias:gestionar` son NUEVOS y deben seedearse en la migración. No existen en migrations previas.

## Goals / Non-Goals

### Goals
- Modelo `SlotEncuentro` con soporte recurrente/fecha única (RN-13), FKs a Asignacion + Materia
- Modelo `InstanciaEncuentro` con estado propio Programado|Realizado|Cancelado (RN-14), slot_id nullable, materia_id, meet_url, video_url, comentario
- Modelo `Guardia` con FK a Asignacion + Materia + Carrera + Cohorte, estado Pendiente|Realizada|Cancelada
- Generación automática de N instancias al crear un slot recurrente (cant_semanas)
- API REST: CRUD slots, CRUD instancias, bloque HTML, CRUD guardias, export CSV
- Guards `encuentros:gestionar` y `guardias:gestionar` nuevos, seedeados en migration
- Scope por rol: PROFESOR/TUTOR filtra por sus asignaciones; COORDINADOR/ADMIN ve todo
- Migración con tablas `slot_encuentro`, `instancia_encuentro`, `guardia` + seed permisos
- Audit log con acciones `ENCUENTRO_CREAR`, `INSTANCIA_EDITAR`, `GUARDIA_REGISTRAR`, `GUARDIA_EDITAR`

### Non-Goals
- Integración real con videoconferencia (Zoom/Meet API) — meet_url es texto libre
- Procesamiento automático de grabaciones (video_url se ingresa manualmente)
- Frontend (React) — lo cubre C-22
- Bloque HTML editable por el usuario (se genera server-side, el usuario lo copia al LMS)
- Guardias recurrentes o schedule (se registran una a una)

## Decisions

### 1. Generación de instancias: síncrona en el servicio

| Opción | Trade-off | Decisión |
|--------|-----------|----------|
| Síncrona en el servicio | Simple, no requiere worker. Si son 50+ semanas, la respuesta tarda. | ✅ **Elegido** — MVP. Cantidad típica: 1 cuatrimestre (~15-20 semanas). |
| Worker asíncrono | No bloquea la respuesta, reintenta si falla | ❌ Sobredimensionado para el volumen esperado |

El servicio `EncuentroService.crear_slot()` recibe los datos del slot, itera desde `fecha_inicio` sumando 7 días `cant_semanas` veces, y hace `session.add_all(instancias)`. Todo dentro de una misma transacción.

```python
# En servicio:
instancias = []
for i in range(slot.cant_semanas):
    fecha = slot.fecha_inicio + timedelta(weeks=i)
    instancias.append(InstanciaEncuentro(
        slot_id=slot.id,
        materia_id=slot.materia_id,
        fecha=fecha,
        hora=slot.hora,
        titulo=f"{slot.titulo} #{i+1}",
        estado="Programado",
        meet_url=slot.meet_url,
    ))
session.add_all(instancias)
```

Para modo fecha única (cant_semanas=0, fecha_unica set): genera 1 instancia.

### 2. Estados de instancia: enum en Python, varchar en DB

Sigue el mismo patrón que `EstadoComunicacion` en C-12.

```python
class EstadoInstancia(str, enum.Enum):
    Programado = "Programado"
    Realizado = "Realizado"
    Cancelado = "Cancelado"
```

Sin transiciones complejas — cualquier estado → cualquier estado. RN-14 establece independencia total. La validación de negocio adicional se agrega en el service si se requiere.

### 3. Scope por rol: filtro en el servicio

Mismo patrón que C-12. El servicio consulta `_get_profesor_asignacion_ids()` (del helper existente en `api/deps.py` o similar) y filtra por `materia_id IN (:asignaciones)`.

- **PROFESOR/TUTOR**: solo ve/opera sobre materias donde tiene asignación activa
- **COORDINADOR/ADMIN**: ve todo el tenant
- **NEXO**: como PROFESOR, por su scope de asignación

El filtro se aplica en el servicio (lógica de negocio), no en el repository.

### 4. Bloque HTML (F6.4): render server-side

Se genera una string HTML con los encuentros de una materia en un rango de fechas. Usa `string.Template` con un template HTML mínimo o concatenación directa.

```html
<!-- Output example -->
<div class="encuentros-semana">
  <h3>Encuentros de Programación I</h3>
  <ul>
    <li><strong>Lunes 10/03</strong> - 18:00 hs - Clase #1
      <a href="https://meet.google.com/xxx">Enlace</a></li>
    <li><strong>Lunes 17/03</strong> - 18:00 hs - Clase #2
      <a href="https://meet.google.com/xxx">Enlace</a>
      <a href="https://youtube.com/xxx">Grabación</a></li>
  </ul>
</div>
```

No se usa un template engine pesado. El HTML se genera con f-strings controladas (no hay input del usuario que pueda inyectar HTML — salvo meet_url/video_url que se escapan con `escape()` de html module).

### 5. Guardias: modelo independiente

Las guardias NO se vinculan a encuentros. Son registros independientes de atención a alumnos. Un tutor registra "cubrí guardia de Programación I el lunes de 14 a 15".

El modelo sigue la entidad E11 de la KB exactamente.

```python
class Guardia(Base, TenantScopedMixin, SoftDeleteMixin):
    __tablename__ = "guardia"

    asignacion_id: FK → Asignacion
    materia_id: FK → Materia
    carrera_id: FK → Carrera
    cohorte_id: FK → Cohorte
    dia: str       # día de la semana (Lunes...Domingo)
    horario: str   # "14:00–14:45"
    estado: str    # Pendiente | Realizada | Cancelada
    comentarios: str | None
```

### 6. Permisos nuevos: seed en migration

Se crean permisos `encuentros:gestionar` y `guardias:gestionar` y se asignan a los roles según la matriz de capacidades:

| Permiso | PROFESOR | TUTOR | COORDINADOR | ADMIN |
|---------|----------|-------|-------------|-------|
| `encuentros:gestionar` | ✅ | — | ✅ | ✅ |
| `guardias:gestionar` | ✅ | ✅ | ✅ | ✅ |

La migration inserta en `permission` y `role_permission` siguiendo el patrón de migration 003.

### 7. Slot con fecha única vs recurrente

RN-13 establece modos excluyentes. Se implementa con campos condicionales:

- **Recurrente**: `fecha_unica IS NULL`, `cant_semanas > 0`
- **Único**: `fecha_unica IS NOT NULL`, `cant_semanas = 0`
- **Inválido**: ambos NULL o ambos NOT NULL (se valida en schema con model_validator)

Se valida a nivel Pydantic (schema) con `@model_validator` y a nivel DB con CHECK constraint (opcional — la validación en schema alcanza para MVP).

### 8. Export de guardias: CSV server-side

`GET /api/guardias/export` recibe los mismos filtros que el listado y devuelve `Content-Type: text/csv` con `Content-Disposition: attachment`.

Se usa `csv.writer` de la stdlib sobre un `io.StringIO`. No se agrega dependencia de pandas ni openpyxl.

## Data Flow

```
PROFESOR                              SERVICE                              DB
    │                                    │                                │
    ├─ POST /encuentros/slots ───────────┤                                │
    │  (recurrente: cant_semanas=15) ────┼───────────────────────────────►│ INSERT slot
    │                                    │ Genera 15 instancias           │
    │                                    ├───────────────────────────────►│ INSERT 15 instancias
    │  ◄── slot + 15 instancias ─────────┤                                │
    │                                    │                                │
    ├─ PATCH /encuentros/instancias/{id} ─┤                               │
    │  {estado: "Realizado",              │                                │
    │   video_url: "https://..."} ────────┼───────────────────────────────►│ UPDATE instancia
    │  ◄── instancia actualizada ─────────┤                                │
    │                                    │                                │
    ├─ GET /encuentros/instancias/{id}/html ─┤                            │
    │  ◄── bloque HTML ──────────────────┤                                │
    │                                    │                                │
    │  [GUARDIAS]                         │                                │
    │                                    │                                │
TUTOR                                     │                                │
    │                                    │                                │
    ├─ POST /guardias ───────────────────┤                                │
    │  {materia_id, dia, horario, ...} ───┼───────────────────────────────►│ INSERT guardia
    │  ◄── guardia creada ───────────────┤                                │
    │                                    │                                │
    ├─ GET /guardias/export ─────────────┤                                │
    │  ◄── CSV attachment ───────────────┤                                │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/slot_encuentro.py` | Create | Modelo `SlotEncuentro` — recurrencia/fecha única, FKs, timestamps |
| `backend/app/models/instancia_encuentro.py` | Create | Modelo `InstanciaEncuentro` — estado propio, slot_id nullable, video_url |
| `backend/app/models/guardia.py` | Create | Modelo `Guardia` — registro independiente de guardia |
| `backend/app/models/__init__.py` | Modify | Export SlotEncuentro, InstanciaEncuentro, Guardia, EstadoInstancia, EstadoGuardia |
| `backend/app/repositories/encuentro_repository.py` | Create | SlotEncuentroRepository + InstanciaEncuentroRepository |
| `backend/app/repositories/guardia_repository.py` | Create | GuardiaRepository |
| `backend/app/repositories/__init__.py` | Modify | Export nuevos repos |
| `backend/app/schemas/encuentros.py` | Create | DTOs: slot crear, instancia actualizar, listar, HTML response |
| `backend/app/schemas/guardias.py` | Create | DTOs: crear, listar, actualizar, export |
| `backend/app/services/encuentro_service.py` | Create | Crear slot con generación de instancias, editar instancia, HTML block, scope |
| `backend/app/services/guardia_service.py` | Create | CRUD guardias, export CSV, scope |
| `backend/app/api/v1/routers/encuentros.py` | Create | 6 endpoints /api/encuentros/* |
| `backend/app/api/v1/routers/guardias.py` | Create | 4 endpoints /api/guardias/* |
| `backend/app/main.py` | Modify | Register ambos routers |
| `backend/alembic/versions/011_encuentros_guardias.py` | Create | Tablas slot_encuentro, instancia_encuentro, guardia + seed permisos |

## Interfaces / Contracts

### Router: `POST /api/encuentros/slots` (F6.1/F6.2 — guard: `encuentros:gestionar`)

Crea slot + genera instancias. Dos modos según RN-13.

```json
// Request — recurrente
{
  "materia_id": "uuid",
  "titulo": "Clase de Programación I",
  "hora": "18:00",
  "dia_semana": "Lunes",
  "fecha_inicio": "2026-03-10",
  "cant_semanas": 15,
  "meet_url": "https://meet.google.com/xxx"
}
// Request — fecha única
{
  "materia_id": "uuid",
  "titulo": "Clase inaugural",
  "hora": "18:00",
  "dia_semana": "Lunes",
  "fecha_inicio": "2026-03-10",
  "cant_semanas": 0,
  "fecha_unica": "2026-03-10",
  "meet_url": "https://meet.google.com/yyy"
}
// Response
{
  "slot": { "id": "uuid", "titulo": "...", "cant_semanas": 15, ... },
  "instancias": [
    { "id": "uuid", "fecha": "2026-03-10", "estado": "Programado", ... },
    ...
  ],
  "total_instancias": 15
}
```

### Router: `PATCH /api/encuentros/instancias/{id}` (F6.3 — guard: `encuentros:gestionar`)

```json
// Request (todos opcionales)
{
  "estado": "Realizado",
  "meet_url": "https://meet.google.com/xxx",
  "video_url": "https://youtube.com/watch?v=xxx",
  "comentario": "Clase grabada con buena participación"
}
// Response — InstanciaEncuentro actualizada
{
  "id": "uuid",
  "estado": "Realizado",
  "video_url": "https://youtube.com/watch?v=xxx",
  ...
}
```

### Router: `GET /api/encuentros/instancias` (guard: `encuentros:gestionar`)

```json
// Query params: materia_id (opcional), desde (opcional), hasta (opcional)
// Response
{
  "items": [
    { "id": "uuid", "fecha": "2026-03-10", "hora": "18:00",
      "titulo": "Clase #1", "estado": "Realizado", "meet_url": "...",
      "video_url": "...", "slot_id": "uuid" }
  ],
  "total": 15
}
```

### Router: `GET /api/encuentros/instancias/{id}/html` (F6.4 — guard: `encuentros:gestionar`)

```json
// Response
{
  "html": "<div class=\"encuentros-semana\">\n  <h3>Encuentros...</h3>\n  ...\n</div>"
}
```

### Router: `GET /api/encuentros/admin` (F6.5 — guard: `encuentros:gestionar` + rol COORDINADOR/ADMIN)

```json
// Query params: materia_id, desde, hasta, estado (todos opcionales)
// Response — mismo schema que list pero SIN scope filter
```

### Router: `POST /api/guardias` (F6.6 — guard: `guardias:gestionar`)

```json
// Request
{
  "asignacion_id": "uuid",
  "materia_id": "uuid",
  "carrera_id": "uuid",
  "cohorte_id": "uuid",
  "dia": "Lunes",
  "horario": "14:00–14:45",
  "comentarios": "Consulta sobre Trabajo Práctico 2"
}
// Response
{
  "id": "uuid",
  "estado": "Pendiente",
  "creada_at": "2026-06-19T10:00:00Z",
  ...
}
```

### Router: `GET /api/guardias` (guard: `guardias:gestionar`)

```json
// Query params: materia_id, desde, hasta, estado (todos opcionales)
// Response
{
  "items": [
    { "id": "uuid", "dia": "Lunes", "horario": "14:00–14:45",
      "estado": "Pendiente", "materia_id": "uuid", ... }
  ],
  "total": 5
}
```

### Router: `GET /api/guardias/export` (guard: `guardias:gestionar`)

```
// Query params: mismos filtros que list
// Response: Content-Type: text/csv, Content-Disposition: attachment
// Headers
dia,horario,estado,materia,carrera,cohorte,comentarios,creada_at
Lunes,14:00-14:45,Pendiente,Programación I,TSDS,2026,Consulta TP2,2026-06-19
```

### Router: `PATCH /api/guardias/{id}` (guard: `guardias:gestionar`)

```json
// Request
{
  "estado": "Realizada",
  "comentarios": "Se resolvieron dudas sobre el TP"
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (pure) | Generación de instancias (cant_semanas, fecha_unica), validación de schema (modos excluyentes), HTML block generation | Test functions directly — no DB needed |
| Unit (pure) | Export CSV, formateo de datos | Test string output directly |
| Integration | Slot repository: CRUD, list por materia | seed_data fixture with real DB |
| Integration | Instancia repository: CRUD, list con filtros, update estado | seed_data fixture |
| Integration | Guardia repository: CRUD, list con filtros, export query | seed_data fixture |
| Integration | Service: crear slot recurrente genera N instancias en DB, crear fecha única genera 1 | seed_data fixture, verify counts |
| Integration | Service: scope filter (PROFESOR ve solo sus materias) | Different role fixtures |
| E2E | Full HTTP flow: crear slot → listar instancias → editar instancia → HTML | httpx AsyncClient |
| E2E | Guardia: crear → listar → export → editar | httpx AsyncClient |
| E2E | Permissions: 403 sin token, 403 sin permiso, 401 | Test with missing guards |
| E2E | Validación: modo inválido (ambos modos seteados) → 422 | Test schema validation |

**Seed data needed**: tenant, materia, usuario (profesor), usuario (coordinador), usuario (tutor), asignaciones para cada rol.

## Migration / Rollout

**Migration 011** (`011_encuentros_guardias.py`):
- `down_revision = "010"`
- `create_table("slot_encuentro")`: id, tenant_id, asignacion_id, materia_id, titulo, hora, dia_semana, fecha_inicio, cant_semanas, fecha_unica (nullable), meet_url, vig_desde, vig_hasta, created_at, updated_at, deleted_at
- `create_table("instancia_encuentro")`: id, tenant_id, slot_id (nullable), materia_id, fecha, hora, titulo, estado, meet_url, video_url (nullable), comentario, created_at, updated_at, deleted_at
- `create_table("guardia")`: id, tenant_id, asignacion_id, materia_id, carrera_id, cohorte_id, dia, horario, estado, comentarios, creada_at, created_at, updated_at, deleted_at
- Índices: `ix_instancia_materia` (tenant_id, materia_id), `ix_instancia_slot` (slot_id), `ix_instancia_fecha` (tenant_id, fecha), `ix_guardia_materia` (tenant_id, materia_id), `ix_guardia_asignacion` (asignacion_id)
- FK: todas con CASCADE/SET NULL según corresponda
- **Seed permisos**: insert en `permission` para `encuentros:gestionar` y `guardias:gestionar`; insert en `role_permission` según matriz del §Decisions

**Rollout order:**
1. Deploy migration 011 (3 tablas vacías + seed permisos)
2. Deploy código (modelos, repos, schemas, services, routers)
3. Verificar que los routers se registran en main.py

**Rollback:** Downgrade migration + redeploy sin routers de encuentros/guardias.

## Open Questions

- [ ] **Dia_semana**: ¿usar enum Python o guardar como string "Lunes"..."Domingo"? Se usa string por simplicidad y para coincidir con el modelo guardia que también usa dia como string.
- [ ] **Bloque HTML**: ¿el template debe ser configurable por tenant o el mismo para todos? MVP: mismo para todos. Si se necesita customización, se agrega template por tenant.
- [ ] **Export guardias**: ¿CSV es suficiente o se necesita también XLSX? MVP: CSV. Si se solicita, se agrega en change futuro.
