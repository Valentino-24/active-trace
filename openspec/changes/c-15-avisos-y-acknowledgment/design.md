# Design: C-15 Avisos y Acknowledgment

## Context

C-12 cubrió comunicaciones salientes (email a alumnos). Pero no hay mecanismo interno para que COORDINADOR/ADMIN comuniquen novedades al equipo docente. Este change implementa el tablón de avisos (F3.5) con segmentación por audiencia, ventana de vigencia y acuse de recibo.

Depende de C-06 porque los avisos se segmentan por materia/cohorte.

## Goals / Non-Goals

### Goals
- Modelo `Aviso` con alcance, severidad, vigencia, orden, requiere_ack
- Modelo `AcknowledgmentAviso` con confirmado_at
- ABM completo (crear, modificar, soft-delete, listar con contadores) — solo COORDINADOR/ADMIN
- Visualización para destinatarios: filtrado por rol/alcance/cohorte/materia (RN-20), ventana de vigencia (RN-18), ordenado por `orden`
- Acuse de recibo: crear ack, listar acuses (solo gestión), ocultar aviso ya acusado (si requiere_ack)
- Contadores derivados (no denormalizados): count de acuses por aviso
- Permiso nuevo `avisos:publicar`

### Non-Goals
- Notificaciones push/email cuando se publica un aviso (lo cubre C-12 si se requiere)
- Avisos con destino a ALUMNO (el tablón es institucional, para el equipo docente)
- Formato enriquecido en el cuerpo (MVP: texto plano con soporte futuro para HTML)
- Programa de publicación (publicar en fecha futura automáticamente)

## Decisions

### 1. Filtrado por audiencia en el servicio (no en DB query compleja)

El endpoint `GET /api/avisos/mis-avisos` recibe el usuario autenticado con su rol, asignaciones (materias), cohorte. El servicio construye el filtro:

```python
# Lógica de filtrado:
stmt = select(Aviso).where(
    Aviso.tenant_id == tenant_id,
    Aviso.activa == True,
    Aviso.inicio_en <= ahora,
    Aviso.fin_en >= ahora,  # RN-18
)
# RN-20: filtrar por alcance
# Si el aviso es Global → todos lo ven
# Si es PorMateria → user debe tener asignación en esa materia
# Si es PorCohorte → user debe pertenecer a esa cohorte
# Si es PorRol → user debe tener ese rol
```

Se implementa como filtros Python/SQLAlchemy progresivos. No es una query monster — los avisos activos por tenant son pocos (decenas, no miles).

### 2. Acknowledgment: ocultar aviso ya acusado

Cuando un usuario hace ack, se crea `AcknowledgmentAviso`. En `mis-avisos`, se excluyen avisos donde:
- `requiere_ack = true` AND existe `AcknowledgmentAviso` para ese usuario y aviso

Esto se implementa con un NOT EXISTS subquery:

```python
# Subquery para excluir avisos ya acusados (si requiere_ack)
if user_acks:
    stmt = stmt.where(
        ~Aviso.requiere_ack |  # si no requiere, siempre se muestra
        ~Aviso.id.in_(user_acked_ids)  # si ya acusó, no se muestra
    )
```

### 3. Contadores derivados: no denormalizar

`GET /api/avisos` (listado de gestión) devuelve contadores:
- `total_vistos`: count de AcknowledgmentAviso para ese aviso
- `total_usuarios_objetivo`: estimación basada en usuarios del tenant con el rol/alcance del aviso (opcional — MVP puede omitir este cálculo pesado y mostrar solo vistos)

```python
async def _count_acks(aviso_id) -> int:
    stmt = select(func.count()).where(
        AcknowledgmentAviso.aviso_id == aviso_id
    )
    result = await session.execute(stmt)
    return result.scalar()
```

### 4. Permiso `avisos:publicar`: COORDINADOR y ADMIN

Según F3.5: "Quién gestión: COORDINADOR, ADMIN".
Se asigna a ambos roles en el seed.

| Permiso | COORDINADOR | ADMIN |
|---------|-------------|-------|
| `avisos:publicar` | ✅ | ✅ |

Para lectura (`GET /api/avisos/mis-avisos`, `POST /api/avisos/{id}/ack`) NO se requiere permiso — cualquier usuario autenticado puede ver y acusar los avisos que le correspondan según su audiencia.

### 5. Orden de presentación

El campo `orden` (entero) define la prioridad. Menor valor = mayor prioridad. Los avisos se ordenan ASC por `orden` y, como tiebreaker, por `created_at DESC`.

### 6. Soft delete en Aviso, sin soft delete en AcknowledgmentAviso

Los avisos siguen el patrón del proyecto (SoftDeleteMixin). Los acknowledgments NO tienen soft delete — son registros de auditoría immutables.

## Data Flow

```
COORDINADOR                    SERVICE                         DB
    │                              │                           │
    ├─ POST /avisos ───────────────┤                           │
    │  {titulo, cuerpo, alcance,   │                           │
    │   rol_destino, vigencia,     │                           │
    │   requiere_ack, orden} ──────┼──────────────────────────►│ INSERT aviso
    │  ◄── aviso creado ──────────┤                           │
    │                              │                           │
    │  [Tiempo después]            │                           │
    ├─ PATCH /avisos/{id} ────────┤                           │
    │  {activo: false} ────────────┼──────────────────────────►│ UPDATE aviso
    │                              │                           │

DOCENTE                          SERVICE                         DB
    │                              │                           │
    ├─ GET /avisos/mis-avisos ─────┤                           │
    │                              ├──► SELECT avisos WHERE    │
    │                              │    activo AND en vigencia │
    │                              │    AND alcance match rol  │
    │                              │    AND NOT already acked  │
    │  ◄── [aviso1, aviso2] ───────┤                           │
    │                              │                           │
    ├─ POST /avisos/{id}/ack ──────┤                           │
    │                              ├──────────────────────────►│ INSERT acknowledgment
    │  ◄── ack registrado ─────────┤                           │
    │                              │                           │
    │  [El aviso ya no aparece]    │                           │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/aviso.py` | Create | Modelo `Aviso` + enums AlcanceAviso, SeveridadAviso |
| `backend/app/models/acknowledgment_aviso.py` | Create | Modelo `AcknowledgmentAviso` |
| `backend/app/models/__init__.py` | Modify | Export nuevos modelos |
| `backend/app/repositories/aviso_repository.py` | Create | AvisoRepository + AcknowledgmentRepository |
| `backend/app/repositories/__init__.py` | Modify | Export nuevos repos |
| `backend/app/schemas/avisos.py` | Create | DTOs request/response |
| `backend/app/services/aviso_service.py` | Create | Lógica completa: CRUD, filtrado audiencia, ack, contadores |
| `backend/app/api/v1/routers/avisos.py` | Create | Endpoints /api/avisos/* |
| `backend/app/main.py` | Modify | Register router |
| `backend/alembic/versions/013_avisos.py` | Create | Tablas aviso + acknowledgment_aviso + seed permiso |

## Interfaces / Contracts

### Router: `POST /api/avisos` (guard: `avisos:publicar`)

```json
// Request
{
  "titulo": "Recordatorio de cierre de actas",
  "cuerpo": "Las actas cierran el 30/06.",
  "alcance": "PorMateria",
  "materia_id": "uuid",
  "cohorte_id": null,
  "rol_destino": "PROFESOR",
  "severidad": "Advertencia",
  "inicio_en": "2026-06-20T00:00:00Z",
  "fin_en": "2026-07-01T00:00:00Z",
  "orden": 1,
  "requiere_ack": true
}
// Response 201 — Aviso creado
```

### Router: `PATCH /api/avisos/{id}` (guard: `avisos:publicar`)

```json
// Request (todos opcionales)
{
  "activo": false,
  "titulo": "Nuevo título",
  "fin_en": "2026-07-15T00:00:00Z"
}
```

### Router: `GET /api/avisos` (guard: `avisos:publicar`)

```json
// Response
{
  "items": [
    {
      "id": "uuid",
      "titulo": "Recordatorio...",
      "alcance": "PorMateria",
      "severidad": "Advertencia",
      "activo": true,
      "inicio_en": "...",
      "fin_en": "...",
      "total_vistos": 15,
      "total_acks": 12,
      "created_at": "..."
    }
  ],
  "total": 3
}
```

### Router: `GET /api/avisos/mis-avisos` (todos los roles autenticados)

```json
// Response — solo avisos visibles para este usuario
{
  "items": [
    {
      "id": "uuid",
      "titulo": "Recordatorio...",
      "cuerpo": "Las actas cierran...",
      "severidad": "Advertencia",
      "orden": 1,
      "requiere_ack": true,
      "ya_ack": false
    }
  ]
}
```

### Router: `POST /api/avisos/{id}/ack` (todos los roles autenticados)

```json
// Response 201
{
  "ack_id": "uuid",
  "aviso_id": "uuid",
  "confirmado_at": "2026-06-19T12:00:00Z"
}
// Response 409 — si requiere_ack es false
{
  "detail": "Este aviso no requiere confirmación"
}
// Response 409 — si ya acusó
{
  "detail": "Ya has confirmado este aviso"
}
```

### Router: `GET /api/avisos/{id}/acks` (guard: `avisos:publicar`)

```json
{
  "items": [
    {
      "usuario_id": "uuid",
      "usuario_email": "docente@mail.com",
      "confirmado_at": "2026-06-19T12:00:00Z"
    }
  ],
  "total": 12
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Filtrado por alcance (Global visible a todos, PorMateria solo con asignación), ventana de vigencia (antes/dentro/después) | Test functions directly |
| Integration | Aviso repo: CRUD, list_activos_para_usuario con filtros combinados | seed_data fixture |
| Integration | Acknowledgment repo: create, count, list_por_aviso, exists | seed_data fixture |
| Integration | Service: crear aviso → visible para usuario correcto → ack → oculto; aviso sin ack sigue visible | seed_data fixture |
| E2E | Full HTTP flow: crear → listar gestión → mis-avisos → ack → mis-avisos (ya no aparece) → listar acuses | httpx AsyncClient |
| E2E | Permissions: 403 sin `avisos:publicar` en endpoints de gestión; 200 en mis-avisos/ack sin permiso | Test guards |
| E2E | Validación: 422 sin campos requeridos, 409 ack duplicado, 409 ack sin requiere_ack | Test edge cases |

## Migration / Rollout

**Migration 013** (`013_avisos.py`):
- `down_revision = "012"`
- `create_table("aviso")`: id, tenant_id, alcance (varchar), materia_id (nullable), cohorte_id (nullable), rol_destino (nullable), severidad (varchar), titulo, cuerpo (text), inicio_en (datetime), fin_en (datetime), orden (integer), activo (bool), requiere_ack (bool), timestamps, deleted_at
- `create_table("acknowledgment_aviso")`: id, aviso_id, usuario_id, confirmado_at, created_at (sin soft delete)
- FK: aviso → tenant, materia, cohorte; acknowledgment → aviso, users
- Seed: permiso `avisos:publicar` en permission + role_permission para COORDINADOR y ADMIN

## Open Questions

- [ ] **Total_usuarios_objetivo**: ¿calcularlo o skip? MVP: solo mostrar `total_vistos` y `total_acks`. Si se requiere saber cuántos debían verlo, se agrega después.
- [ ] **Cuerpo con formato**: ¿texto plano o HTML? MVP: texto plano. El schema acepta string, si después se requiere HTML solo cambia el frontend.
- [ ] **Orden**: ¿se permite orden negativo? Se acepta cualquier entero. El COORDINADOR define la numeración.
