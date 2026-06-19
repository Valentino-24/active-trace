## Why

C-10 ya proveyó la infraestructura para importar calificaciones y configurar umbrales. Sin C-11 esos datos no generan valor — el sistema no puede responder preguntas clave del docente: *¿quiénes están atrasados?, ¿qué actividades tienen mayor/menor aprobación?, ¿cuál es la nota final de cada alumno?* Este change convierte datos crudos en información accionable para PROFESORES, TUTORES, COORDINADORES y ADMIN, cerrando el flujo central de valor importar → analizar → comunicar.

## What Changes

Se agrega un módulo `analisis` (repository + service + schemas + router) bajo `/api/analisis/*` con 8 endpoints de consulta/export. **No requiere nuevos modelos ni migraciones** — todo opera como queries de solo lectura sobre `Calificacion`, `UmbralMateria` y `EntradaPadron`.

Funcionalidades implementadas:
- **F2.2** — Alumnos atrasados (actividades faltantes o nota < umbral, RN-06)
- **F2.3** — Ranking de actividades aprobadas (≥1 aprobada, RN-09)
- **F2.4** — Reportes rápidos por materia (métricas consolidadas)
- **F2.5** — Notas finales agrupadas (promedio simple normalizado)
- **F2.6** — Exportar TPs sin corregir (descargable, textuales RN-07/08)
- **F2.7** — Monitor general de actividades (vista transversal + filtros)
- **F2.8** — Monitor de seguimiento (tutor/profesor, filtrable)
- **F2.9** — Monitor de seguimiento (coordinación/admin, + rango fechas)

## Capabilities

### New Capabilities
- `analisis`: Consultas analíticas y reportes sobre calificaciones — alumnos atrasados, ranking, reportes rápidos, notas finales agrupadas, export de TPs sin corregir, monitores de seguimiento con filtros. Guard `atrasados:ver` con scope `(propio)` para PROFESOR.

### Modified Capabilities
None

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/api/v1/routers/analisis.py` | New | Router con endpoints F2.2–F2.9 bajo `/api/analisis/*` |
| `backend/app/services/analisis_service.py` | New | Lógica de cómputo: atrasados, ranking, notas finales, métricas |
| `backend/app/repositories/analisis_repository.py` | New | Queries analíticas sobre `Calificacion`, `UmbralMateria`, `EntradaPadron` |
| `backend/app/schemas/analisis.py` | New | Pydantic DTOs para requests/responses de analisis |
