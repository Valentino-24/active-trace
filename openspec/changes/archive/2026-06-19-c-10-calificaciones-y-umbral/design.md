# Design: Calificaciones y Umbral

## Technical Approach

Mismo patrón **preview → confirm** que C-09: servidor parsea archivo LMS, clasifica columnas numéricas (`(Real)` suffix, RN-01) vs textuales (RN-02), devuelve preview → cliente selecciona actividades → confirma. `aprobado` se computa en service al insertar contra el `UmbralMateria` vigente. Herencia simple: si no existe umbral para `asignacion_id` específico, cae al default de materia (`asignacion_id IS NULL`).

## Architecture Decisions

| # | Decisión | Choice | Rationale |
|---|----------|--------|-----------|
| 1 | Preview state | **Client-side** (mismo que C-09) | Preview devuelve datos parseados; confirm los recibe. 0 estado servidor, simplicidad. |
| 2 | File parser | **Nuevo en services/calificaciones.py** | Formato LMS tiene columnas variables (cada actividad es una columna). No reutiliza parser C-09. |
| 3 | `aprobado` storage | **Columna booleana, computada al insertar** | Propiedad híbrida requiere join a UmbralMateria en cada query. Umbral cambia poco; recalcular masivo es post-MVP. |
| 4 | Umbral fallback | **`asignacion_id` → `asignacion_id IS NULL` → defaults** | RN-03: scope por docente. Si no hay umbral específico, se usa el de materia. |
| 5 | `max_nota` | **Del archivo LMS (row "Calificación máxima")**; fallback a 100 | Necesario para `aprobado = nota >= umbral_pct * max_nota` |
| 6 | FK alumno | **`entrada_padron_id` (KB E7) + `usuario_id` denormalizado** | Match por `email_hash` como C-09. Denormalizado para queries sin JOIN. |

## Data Flow

```
POST /preview ──→ parser → columnas_detectadas [{nombre, tipo, max_nota}] + filas
                        ↕ (cliente selecciona actividades)
POST /import  ──→ service.importar()
                     ├── match alumno → EntradaPadron
                     ├── lookup umbral → UmbralMateria (herencia)
                     ├── compute aprobado
                     ├── bulk create Calificacion
                     └── audit CALIFICACIONES_IMPORTAR

PUT /umbrales/{id} ──→ update umbral_pct / valores_aprobatorios
```

## File Changes

| File | Action |
|------|--------|
| `models/calificacion.py` | Create — `Calificacion` (TenantScopedMixin + SoftDeleteMixin) |
| `models/umbral_materia.py` | Create — `UmbralMateria` (TenantScopedMixin + SoftDeleteMixin) |
| `schemas/calificacion.py` | Create — DTOs preview, import, list |
| `schemas/umbral_materia.py` | Create — DTOs update/response |
| `repositories/calificacion_repository.py` | Create — bulk insert, list con filtros |
| `repositories/umbral_materia_repository.py` | Create — get_effective, CRUD |
| `services/calificaciones.py` | Create — parseo LMS, column detection, aprobado derivation |
| `services/umbral.py` | Create — get_effective (herencia), validación RN-03 |
| `api/v1/routers/calificaciones.py` | Create — 6 endpoints |
| `alembic/versions/009_crear_calificacion_umbral.py` | Create — tablas `calificacion`, `umbral_materia` |
| `api/v1/routers/__init__.py` | Modify — registrar router |
| RBAC seed | Modify — permisos `calificaciones:importar`, `calificaciones:ver` |

## Interfaces / Contracts

### Modelos (resumen)

```python
class Calificacion(Base, TenantScopedMixin, SoftDeleteMixin):
    entrada_padron_id: FK → EntradaPadron
    materia_id / cohorte_id / asignacion_id: FK
    usuario_id: FK → User (denormalizado)
    actividad_nombre: str(255)
    nota: Decimal(6,2) | None        # RN-01: columna (Real)
    nota_textual: str(100) | None    # RN-02: textual
    aprobado: bool                   # derivado en service
    origen: str(20)                  # Importado | Manual
    metadata: JSONB | None           # max_nota por actividad
    periodo: str(20)

class UmbralMateria(Base, TenantScopedMixin, SoftDeleteMixin):
    materia_id / cohorte_id: FK
    asignacion_id: FK | None          # NULL = default materia
    umbral_pct: Decimal(4,3) default=0.600
    valores_aprobatorios: ARRAY(String(100))
```

### Endpoints

| Method | Path | Guard |
|--------|------|-------|
| POST | `/api/calificaciones/preview` | `calificaciones:importar` |
| POST | `/api/calificaciones/import` | `calificaciones:importar` |
| POST | `/api/calificaciones/importar-finalizacion` | `calificaciones:importar` |
| GET | `/api/calificaciones?materia_id=&cohorte_id=` | `calificaciones:ver` |
| GET | `/api/umbrales?materia_id=&cohorte_id=` | `calificaciones:ver` |
| PUT | `/api/umbrales/{id}` | `calificaciones:importar` |

### Aprobado derivation

```python
def calcular_aprobado(nota, nota_textual, umbral, max_nota) -> bool:
    if nota is not None:
        return nota >= umbral.umbral_pct * max_nota
    if nota_textual:
        return nota_textual in (umbral.valores_aprobatorios or [])
    return False
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | `calcular_aprobado`: numérica, textual, sin nota | pytest parametrized, 0 mocks |
| Unit | Column detection: `(Real)` → numérica | pytest parametrized |
| Unit | Umbral inheritance: específico → fallback → default | pytest parametrized |
| Integration | Preview parsea .xlsx/.csv real | httpx.AsyncClient + DB real |
| Integration | Import bulk insert + aprobado + audit | httpx, verificar BD y AuditLog |
| Integration | Finalizacion detecta TPs sin nota | httpx |
| Integration | List filtra por materia+cohorte | httpx |
| Integration | PUT umbral actualiza scope | httpx |

## Migration

`alembic/versions/009_crear_calificacion_umbral.py` — crea tablas con índices compuestos `(materia_id, cohorte_id)`, FKs con cascade. Rollback: `alembic downgrade -1` + eliminar archivos.

## Open Questions

- [ ] `max_nota`: ¿del archivo LMS o default 100?
- [ ] Formato exacto del archivo de finalización (F1.2) — ¿misma estructura que calificaciones?
- [ ] `calificaciones:ver` scope: ¿PROFESOR solo ve propias, COORDINADOR/ADMIN todas? (mismo patrón C-09)
