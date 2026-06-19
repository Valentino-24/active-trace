# Design: C-12 Comunicaciones — Cola y Worker

## Context

C-11 ya detecta atrasados y genera reportes. Sin este change el flujo importar → analizar → comunicar queda trunco: el docente sabe quién está atrasado pero no puede actuar. C-12 cierra el canal de comunicación saliente con preview obligatorio (RN-16, F3.1), cola asíncrona con máquina de estados (RN-15, F3.2), y aprobación configurable por tenant (RN-17, F3.3).

Es el último change del camino crítico (GATE 9) y prerrequisito del frontend docente (C-22).

Los permisos `comunicacion:enviar` y `comunicacion:aprobar` ya están seedeados en migration 003 (003_crear_rbac.py), asignados a PROFESOR, COORDINADOR, NEXO y ADMIN según corresponda. No requieren reseed.

## Goals / Non-Goals

**Goals:**
- Modelo `Comunicacion` con tenant-scope, destinatario cifrado AES-256, máquina de estados (Pendiente→Enviando→Enviado/Error/Cancelado), y campos de aprobación (aprobado_por, fecha_aprobacion)
- Worker asíncrono que consume mensajes Pendiente por lote, transiciona estados, aplica templates con `string.Template`
- Preview obligatorio (F3.1, RN-16) con sustitución de variables: `${nombre}`, `${materia}`, `${comision}`, etc.
- Envío masivo con lote_id que agrupa N destinatarios (F3.2)
- Aprobación configurable por tenant: flag `requiere_aprobacion_comunicaciones` en settings del tenant (F3.3, RN-17)
- API REST completa con guards `comunicacion:enviar` y `comunicacion:aprobar`
- Migración 010 que crea la tabla `comunicacion` (sin reseed de permisos — ya existen)
- Audit log con acción `COMUNICACION_ENVIAR` (lote_id, cantidad destinatarios, resultado)

**Non-Goals:**
- Integración real con SMTP/Mailgun/SendGrid (MVP usa logging del contenido)
- Mensajería interna (F3.4) o tablón de avisos (F3.5) — quedan para changes posteriores
- Panel de tracking en frontend (lo consume C-22)
- Plantillas persistentes editables por el usuario (las templates van inline en el request por ahora)

## Decisions

### 1. Worker: asyncio background task en el mismo proceso

| Opción | Trade-off | Decisión |
|--------|-----------|----------|
| asyncio task en lifespan | Simple, sin infra adicional. Si crashea, muere con el proceso. Requiere restart del contenedor. | ✅ **Elegido** — MVP, 0 deuda operativa |
| Celery/ARQ separado | Aísla crashes, escala independiente, reintentos nativos | ❌ Sobredimensionado para MVP. Si el throughput futuro lo exige (1000+ msg/día), se migra a tarea separada |

Implementación: `workers/comunicacion_worker.py` con clase `ComunicacionWorker` que recibe session_factory + settings. Se arranca en `lifespan` como `asyncio.create_task()`. Bucle: poll cada 10s, batch de 50, sleep si no hay pendientes.

```python
# En lifespan, después de crear engine:
worker = ComunicacionWorker(
    session_factory=app.state.async_session_factory,
    settings=settings,
)
worker_task = asyncio.create_task(worker.run())
app.state.worker_task = worker_task

# En shutdown:
worker_task.cancel()
```

### 2. Template engine: Python `string.Template`

| Opción | Trade-off | Decisión |
|--------|-----------|----------|
| `string.Template` | Built-in, seguro por defecto (`$$` escapa `$`). Sin AST injection. | ✅ **Elegido** |
| `str.format()`/f-strings | Evaluación arbitraria si el template es user-provided | ❌ Riesgo de inyección |
| Jinja2 | Poderoso pero pesado para templates planos de 2-3 variables | ❌ Sobredimensionado |

Variables disponibles: `${nombre}`, `${apellido}`, `${materia}`, `${comision}`, `${nombre_profesor}`. El template se pasa inline en el request (campo `asunto_template`, `cuerpo_template` del schema).

### 3. Aprobación: lote-level e individual

RN-17 requiere que envíos masivos pasen por aprobación. Se implementan dos niveles:

- **Lote-level**: `POST /api/comunicaciones/aprobar/{lote_id}` transiciona todos los Pendiente del lote a Enviando (o Error si hay mezcla de estados).
- **Individual**: `POST /api/comunicaciones/aprobar/{comunicacion_id}/individual` para casos donde un solo destinatario necesita revisión.
- Si el tenant NO requiere aprobación (`requiere_aprobacion_comunicaciones = false`), el worker procesa Pendiente directamente.

El flag del tenant se almacena en `tenant.config` (JSONB) o como columna directa — se define en la migración del modelo si ya existe el campo o si se agrega. Se consulta desde el servicio antes de crear el lote.

### 4. Email sending: log-only para MVP

El worker registra el envío en logs estructurados JSON con `level=INFO`, `action=comunicacion_enviar`, `comunicacion_id`, `destinatario` (hash), `lote_id`. No conecta con SMTP.

Esto permite verificar el flujo completo (creación → cola → worker → transición de estados) sin dependencias externas. La integración real con SMTP/Mailgun se agrega en un change futuro sin cambiar la interfaz del worker — solo reemplaza el método `_enviar()`.

### 5. Scope por rol

- **PROFESOR**: solo ve/envía comunicaciones de sus propias materias (filtro por `asignacion.usuario_id == current_user.id`)
- **COORDINADOR/ADMIN**: ve/envía sobre cualquier materia del tenant
- **NEXO**: similar a PROFESOR pero con su scope de asignación

El filtro se implementa en el servicio, no en el repository, porque depende del rol del usuario (lógica de negocio), no de la entidad.

### 6. Migración 010 — tabla `comunicacion`

Sigue el patrón de migrations anteriores: `sa.*` operations, FK explícitas, índices, y seed de permisos.

```python
# No reseedear permisos — ya existen desde 003.
# Solo crear tabla comunicacion.
```

## Data Flow

```
PROFESOR                         WORKER (async)                   DB
    │                                │                           │
    ├─ POST /preview ────────────────┤  Renderiza template       │
    │   ◄── preview con vars ────────┤  (no persiste)           │
    │                                │                           │
    ├─ POST /enviar ─────────────────┤                           │
    │   (crea lote Pendiente) ───────┼──────────────────────────►│ INSERT comunicacion
    │   ◄── lote_id ─────────────────┤                           │ (estado=Pendiente)
    │                                │                           │
    │         [si requiere aprobación]                            │
    │                                │                           │
COORDINADOR                          │                           │
    │                                │                           │
    ├─ POST /aprobar/{lote_id} ──────┤                           │
    │                                ├──────────────────────────►│ UPDATE estado=Enviando
    │                                │                           │
    │         [worker loop]                                       │
    │                                │                           │
    │                                ├──► SELECT Pendientes      │
    │                                │    (batch 50, limit)      │
    │                                │                           │
    │                                ├──► por cada uno:          │
    │                                │    UPDATE estado=Enviando  │
    │                                │    _enviar() (log)         │
    │                                │    UPDATE estado=Enviado   │
    │                                │       o Error             │
    │                                │                           │
    ├─ GET /estadisticas ────────────┤                           │
    │   ◄── counts by estado ────────┼──────────────────────────►│ SELECT count,group
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/comunicacion.py` | Create | Modelo `Comunicacion` — estado machine, tenant-scope, destinatario cifrado, aprobación, lote_id, timestamps |
| `backend/app/models/__init__.py` | Modify | Export `Comunicacion` |
| `backend/app/repositories/comunicacion_repository.py` | Create | CRUD + `list_pendientes(limit)`, `list_by_lote(lote_id)`, `update_estado()`, `count_by_estado(materia_id)`, `list_pendientes_de_aprobacion()` |
| `backend/app/repositories/__init__.py` | Modify | Export `ComunicacionRepository` |
| `backend/app/schemas/comunicaciones.py` | Create | Schemas: `PreviewRequest`, `PreviewResponse`, `EnvioRequest`, `LoteResponse`, `AprobarRequest`, `EstadisticasResponse`, `ComunicacionResponse` |
| `backend/app/services/comunicacion_service.py` | Create | `preview()`, `enviar()`, `aprobar_lote()`, `aprobar_individual()`, `cancelar_lote()`, `get_estadisticas()`, `get_estado_lote()` |
| `backend/app/api/v1/routers/comunicaciones.py` | Create | 8 endpoints con guards (ver §Interfaces) |
| `backend/app/workers/comunicacion_worker.py` | Create | `ComunicacionWorker` — bucle asyncio, batch polling, template render, state transitions |
| `backend/app/workers/__init__.py` | Create | Package init for workers module |
| `backend/app/core/config.py` | Modify | + `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password` (opcionales para futuro); + campo `worker_poll_interval`, `worker_batch_size` |
| `backend/app/core/templates/__init__.py` | Create | Package init (directorio para templates, aunque MVP los recibe inline) |
| `backend/app/main.py` | Modify | Import worker, arrancar/cancelar en `lifespan`, registrar router |
| `backend/alembic/versions/010_crear_comunicacion.py` | Create | Tabla `comunicacion` — no reseed de permisos |

## Interfaces / Contracts

### Router: `POST /api/comunicaciones/preview` (F3.1 — guard: `comunicacion:enviar`)

```json
// Request
{
  "materia_id": "uuid",
  "destinatarios": ["email1", "email2"],
  "asunto_template": "Aviso importante ${materia}",
  "cuerpo_template": "Hola ${nombre}, tu materia ${materia}..."
}
// Response
{
  "items": [
    {
      "email": "email1",
      "asunto": "Aviso importante Programación I",
      "cuerpo": "Hola Juan, tu materia Programación I..."
    }
  ],
  "total": 2
}
```

### Router: `POST /api/comunicaciones/enviar` (F3.2 — guard: `comunicacion:enviar`)

```json
// Request (mismos campos que preview + confirmacion: true)
{
  "materia_id": "uuid",
  "destinatarios": ["email1", "email2"],
  "asunto_template": "...",
  "cuerpo_template": "...",
  "confirmacion": true
}
// Response
{
  "lote_id": "uuid",
  "total": 2,
  "estado": "Pendiente",
  "requiere_aprobacion": false
}
```

### Router: `POST /api/comunicaciones/aprobar/{lote_id}` (F3.3 — guard: `comunicacion:aprobar`)

```json
// Response
{
  "lote_id": "uuid",
  "total_aprobados": 2,
  "estado": "Enviando"
}
```

### Router: `GET /api/comunicaciones/estadisticas?materia_id=` (guard: `comunicacion:enviar`)

```json
{
  "Pendiente": 5,
  "Enviando": 0,
  "Enviado": 120,
  "Error": 2,
  "Cancelado": 1,
  "total": 128
}
```

### Worker Interface (internal)

```python
class ComunicacionWorker:
    def __init__(self, session_factory, settings):
        """session_factory: async_sessionmaker, settings: Settings"""

    async def run(self):
        """Main loop: poll → process → sleep"""

    async def _poll(self) -> Sequence[Comunicacion]:
        """Fetch next Pendiente batch (configurable limit)"""

    async def _process(self, msg: Comunicacion):
        """Render template, log send, transition state"""
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (pure) | Template rendering, state transition validation, preview logic | Test functions directly — no DB needed |
| Integration | Repository queries (list_pendientes, update_estado, count_by_estado) | seed_data fixture with real DB (AsyncSession) |
| Integration | Service methods (enviar, aprobar_lote, cancelar_lote) | seed_data fixture, verify state transitions in DB |
| Integration | Worker poll + process cycle | Mock _enviar(), verify state changes from Pendiente→Enviado/Error |
| E2E | Full HTTP flow: preview → enviar → worker processes → consultar estadisticas | httpx AsyncClient against test app, real DB |
| Permission | Each endpoint returns 403 when missing required guard | Test with user without comunicacion:enviar / comunicacion:aprobar |
| Scope | PROFESOR sees own materia only, COORD/ADMIN sees all | Test with different role fixtures |

**Seed data needed**: tenant, materia, usuario (profesor), usuario (coordinador), entries in EntradaPadron for template variable resolution.

## Migration / Rollout

**Migration 010** (`010_crear_comunicacion.py`):
- `down_revision = "009"`
- `create_table("comunicacion")` con: id, tenant_id, enviado_por, materia_id, destinatario, asunto, cuerpo, estado (varchar, no enum nativo para evitar casts en migraciones), lote_id, aprobado_por, fecha_aprobacion, enviado_at, created_at, updated_at, deleted_at
- Índices: `ix_comunicacion_lote` (lote_id), `ix_comunicacion_estado` (tenant_id, estado, deleted_at) para poll rápido del worker, `ix_comunicacion_materia` (materia_id) para dashboard
- FK: tenant_id→tenant, enviado_por→users, materia_id→materia, aprobado_por→users
- `NO` reseedear comunicacion:enviar ni comunicacion:aprobar — ya existen desde migration 003

**Rollout order**:
1. Deploy migration 010 (tabla vacía)
2. Deploy código (modelo, repo, service, router, worker)
3. Worker arranca automáticamente con el lifespan

**Rollback**: Downgrade migration + redeploy sin worker.

## Open Questions

- [ ] **Template storage**: ¿Las plantillas se pasan inline en cada request (MVP) o se persisten como configuración del tenant? Decisión MVP: inline. Si la UX lo exige, se migra a templates persistentes.
- [ ] **Worker crash recovery**: Si el worker crashea a mitad de un batch, los mensajes quedan en `Enviando` (estado "colgado"). ¿Agregar timeout que revierta a Pendiente mensajes en Enviando por más de N minutos? Se agrega como mejora post-MVP si se observa el problema.
- [ ] **Tamaño de batch**: ¿50 está bien como default o debe ser configurable por tenant? Se usa setting global. Si un tenant tiene batches de 1000+, se ajusta.
