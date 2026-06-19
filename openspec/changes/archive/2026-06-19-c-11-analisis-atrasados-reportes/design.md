# Design: C-11 Análisis — Atrasados y Reportes

## Context

C-10 estableció `Calificacion` y `UmbralMateria` con datos importados. C-11 es el primer consumidor analítico de esos datos: 8 endpoints read-only que transforman calificaciones crudas en información accionable para docentes y coordinación. No requiere nuevos modelos ni migraciones — todo opera sobre `Calificacion`, `EntradaPadron` (vía `VersionPadron` activa) y `UmbralMateria`.

## Technical Approach

Módulo `analisis` autocontenido con 4 archivos nuevos siguiendo el patrón existente: Router → Service → Repository. Todas las queries son agregaciones SQL (GROUP BY, LEFT JOIN, COUNT) ejecutadas con lecturas consistentes. Sin escrituras, sin transacciones largas.

Scope PROFESOR se resuelve en el router usando el mismo helper `_get_profesor_asignacion_ids()` de C-10, limitando resultados a su `asignacion_id`.

## Architecture Decisions

### Decision: Repositorio propio vs. reusar repos existentes

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| `AnalisisRepository` nuevo | Queries cross-model, no usa `_stmt()` de `BaseRepository` | ✅ Elegido |
| Inyectar `CalificacionRepository` + `EntradaPadronRepository` | Servicio coordinando 2-3 repos, más acoplamiento | ❌ Rechazado |

**Rationale**: Las queries analíticas cruzan múltiples tablas (LEFT JOIN con agregación) y no encajan en el patrón `_model_cls` de `BaseRepository`. Un repositorio dedicado con `self._session.execute()` directo y filtros de tenant manuales es más claro que orquestar 3 repos desde el service.

### Decision: Detección de atrasados vía `aprobado` precomputado

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| Usar `aprobado` de `Calificacion` | Ya está derivado al importar (C-10) | ✅ Elegido |
| Recalcular contra umbral en cada query | Costoso, duplica lógica de C-10 | ❌ Rechazado |

**Rationale**: `aprobado` ya refleja la regla RN-06 (nota < umbral) porque fue derivado contra `UmbralMateria` en el import. Para actividades sin registro (`missing`), simplemente no existe fila en `Calificacion`. Un LEFT JOIN entre `EntradaPadron` y `Calificacion` cubre ambos casos: `c.id IS NULL` (falta) o `c.aprobado = false` (no alcanza umbral).

### Decision: Nuevo permiso `atrasados:ver`

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| Reusar `calificaciones:ver` | Mezcla alcances: ver notas ≠ ver análisis | ❌ Rechazado |
| `atrasados:ver` nuevo | Permiso granular, independiente | ✅ Elegido |

**Rationale**: Las funciones analíticas son un módulo de reporting diferente a la consulta de calificaciones. Un permiso específico permite asignarlo a TUTOR sin dar acceso a notas individuales. Debe crearse en el RBAC seed data (tenant setup).

### Decision: Export CSV sin librería externa

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| `csv.writer` + `StreamingResponse` | Sin dependencias, simple | ✅ Elegido |
| `openpyxl` para XLSX | Dependencia adicional, más complejo | ❌ Rechazado |

**Rationale**: La exportación F2.6 es texto plano (CSV), no requiere XLSX. Usar el módulo `csv` de stdlib con `StreamingResponse(media_type="text/csv")`.

## Data Flow

```
Cliente
  │ GET /api/analisis/atrasados?materia_id=&cohorte_id=
  ▼
Router (analisis.py)
  │ Guard: require_permission("atrasados:ver")
  │ Scope: _get_profesor_asignacion_ids() → filtra si PROFESOR
  ▼
Service (analisis_service.py)
  │ Coordina llamadas al repositorio
  │ Post-procesa: arma dicts de respuesta, calcula métricas
  ▼
Repository (analisis_repository.py)
  │ Queries directas con tenant scope manual (no _stmt())
  │ LEFT JOIN entrada_padron ↔ calificacion
  │ GROUP BY actividad_nombre, alumno
  ▼
DB (PostgreSQL)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/api/v1/routers/analisis.py` | Create | 8 endpoints bajo `/api/analisis/*` con guard `atrasados:ver` |
| `backend/app/services/analisis_service.py` | Create | Lógica de cómputo: atrasados, ranking, notas finales, métricas, monitores |
| `backend/app/repositories/analisis_repository.py` | Create | Queries analíticas multi-tabla (LEFT JOIN, GROUP BY, COUNT) |
| `backend/app/schemas/analisis.py` | Create | Schemas Pydantic para request/response de cada endpoint |
| `backend/app/main.py` | Modify | Agregar `include_router(analisis_router, prefix="/api/analisis")` |
| `backend/tests/test_analisis.py` | Create | Tests E2E + unitarios contra DB real |

## Interfaces / Contracts

```python
# schemas/analisis.py

class AlumnoAtrasado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entrada_padron_id: uuid.UUID
    alumno: str  # "Apellidos, Nombre"
    actividades_faltantes: list[str]
    actividades_desaprobadas: list[str]
    total_atrasos: int

class RankingActividad(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actividad_nombre: str
    total_alumnos: int
    aprobados: int
    porcentaje_aprobacion: float

class ReporteMateria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_alumnos: int
    atrasados: int
    sin_corregir: int
    porcentaje_aprobacion: float

class NotaFinalAlumno(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entrada_padron_id: uuid.UUID
    alumno: str
    promedio: float | None
    actividades_aprobadas: int
    actividades_total: int

class MonitorGeneral(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[MetricaFiltrada]
    total: int
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Cálculo de atrasados (lógica pura) | Funciones sin DB que reciben listas y devuelven dicts |
| Integration | Cada endpoint con datos seed | `seed_data` fixture (mismo patrón C-10), assert estructura + valores |
| Integration | Scope PROFESOR | PROFESOR con asignación A no ve alumnos de B |
| Integration | Multitenant | Otro tenant no ve datos de tenant primario (`other_auth_token`) |
| E2E | Flujo completo: seed → consultar → exportar | HTTPX `AsyncClient` contra DB real |

No requiere mocks de DB — usar fixture `seed_data` real como en C-10.

## Migration / Rollout

No migration requerida. El permiso `atrasados:ver` debe existir en el seed de RBAC del tenant (data migration fuera del scope de este change — asumir que el tenant setup lo crea).

## Open Questions

- [ ] ¿El ranking (F2.3) debe incluir actividades sin ninguna aprobada? Spec dice "solo ≥1 aprobada" — confirmar si es filtro estricto.
- [ ] Monitor general (F2.7): ¿filtro por regional y comisión implica JOIN contra `EntradaPadron`? Sí, esos campos están en `EntradaPadron`, no en `Calificacion`.
- [ ] Notas finales (F2.5): ¿promedio solo de notas numéricas? Las textuales no tienen valor numérico — asumimos `nota IS NOT NULL` para el promedio.
