# Proposal: Calificaciones y Umbral

## Intent

Darle al PROFESOR la capacidad de importar calificaciones desde archivos exportados del LMS (F1.1), detectar entregas sin corregir (F1.2) y configurar el umbral de aprobación por materia (F2.1). Sin esto el sistema no tiene datos de notas para computar atrasados ni rankings (C-11).

## Scope

### In Scope
- Modelos `Calificacion` (E7) y `UmbralMateria` (E8) con soft delete + tenant isolation
- Importar calificaciones (F1.1): subir archivo → detectar columnas numéricas `(Real)` (RN-01) y textuales (RN-02) → preview → seleccionar actividades → confirmar
- Importar reporte de finalización (F1.2): detectar TPs textuales entregados sin nota
- Derivación automática de `aprobado` (numérica vs umbral, textual vs conjunto aprobatorio)
- Configurar umbral por asignación docente (F2.1, RN-03, defecto 60%) — no afecta otros docentes
- Audit `CALIFICACIONES_IMPORTAR` por cada import
- `Migración 0NN: calificacion, umbral_materia`
- Permiso `calificaciones:importar`
- Tests: derivación aprobado, import + preview, selección de actividades, umbral scope por asignación

### Out of Scope
- Cómputo de atrasados y ranking (C-11)
- UI frontend
- Sincronización automática con LMS (on-demand igual que C-09)
- Umbral global del tenant (solo por asignación)

## Capabilities

### New Capabilities
- `calificaciones`: importar calificaciones desde archivo LMS con detección de columnas (RN-01/RN-02), preview, selección de actividades, confirmación, derivación de `aprobado`, import de reporte de finalización
- `umbral-materia`: configurar umbral_pct y valores aprobatorios textuales por asignación docente, con defecto 60%

### Modified Capabilities
- None

## Approach

- Mismo patrón que C-09 (padron): flujo **preview → confirm** en dos endpoints, parseo con openpyxl/csv
- `Calificacion` linkeada a `EntradaPadron` (E7 KB): FK `entrada_padron_id` + `materia_id`
- Columnas numéricas detectadas por sufijo `(Real)` en encabezado (RN-01); textuales por contenido no numérico
- `UmbralMateria` linkeado a `Asignacion` (scope por docente, RN-03): `asignacion_id` + `materia_id`
- `aprobado` es campo derivado en servidor al insertar/consultar (no almacenado, o recalculado siempre)
- Audit `CALIFICACIONES_IMPORTAR` con `{materia_id, actividad, total_notas, modo}`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/calificacion.py` | New | Modelo `Calificacion` |
| `backend/app/models/umbral_materia.py` | New | Modelo `UmbralMateria` |
| `backend/app/schemas/calificacion.py` | New | Pydantic DTOs |
| `backend/app/schemas/umbral_materia.py` | New | Pydantic DTOs |
| `backend/app/api/v1/routers/calificaciones.py` | New | Endpoints import/preview/umbral |
| `backend/app/services/calificaciones.py` | New | Lógica de import + derivación aprobado |
| `backend/app/services/umbral.py` | New | Lógica de umbral |
| `backend/app/repositories/calificacion.py` | New | Repository tenant-scoped |
| `backend/app/repositories/umbral_materia.py` | New | Repository tenant-scoped |
| `migrations/versions/0NN_calificacion_umbral.py` | New | Migration |
| Permisos | New | `calificaciones:importar` (PROFESOR, COORDINADOR, ADMIN) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Archivo LMS con columnas no estándar | Medium | Preview muestra errores; usuario selecciona actividades manualmente |
| Umbral de docente A altera cómputo de docente B | Low | Scoped por `asignacion_id` — solo afecta datos del docente que lo configura |
| Volumen grande de calificaciones (>10K) | Low | Preview limitada a 10K filas; import batch transaccional |

## Rollback Plan

1. `alembic downgrade -1` para revertir migration 0NN
2. Eliminar archivos nuevos: modelos, routers, services, repositories, schemas
3. Remover permiso `calificaciones:importar` del seed
4. Datos con soft delete existentes se conservan inactivos (no hay hard delete)

## Dependencies

- C-09 ✅ (padron-ingesta-moodle: `EntradaPadron` existe como FK de `Calificacion`)

## Success Criteria

- [ ] Preview detecta columna `(Real)` como numérica y valores "Satisfactorio"/"Supera lo esperado" como textuales aprobatorios
- [ ] Import confirma calificaciones vinculadas a `EntradaPadron` correctas
- [ ] `aprobado` se deriva correctamente: numérica ≥ umbral → true; textual ∈ conjunto aprobatorio → true; resto → false
- [ ] Umbral configurado para asignación A no afecta asignación B (misma materia, distinto docente)
- [ ] Audit `CALIFICACIONES_IMPORTAR` se registra en cada import con detalle
