## Why

C-13 completó encuentros y guardias (Épica 6). El siguiente dominio académico del camino crítico son los coloquios (Épica 7): la evaluación oral final que cierra el ciclo del alumno en una materia.

Sin este change, el sistema puede planificar encuentros, registrar guardias, detectar atrasados y comunicar, pero no puede convocar a coloquios — el hito más crítico del calendario académico formal. Es dependencia directa de C-22 (frontend docente) y del flujo completo de liquidaciones (C-18) — no se puede liquidar sin cerrar coloquios.

Cubre F7.1–F7.5 del PRD y FL-07 completo.

## What Changes

Nuevo módulo `coloquios` con gestión de convocatorias, reserva de turnos por ALUMNO, y registro de resultados.

### Modelos
- **`Evaluacion`**: convocatoria de evaluación oral (materia, cohorte, tipo, instancia, días_disponibles). Representa "el coloquio de Programación I del 2026-1".
- **`ReservaEvaluacion`**: turno reservado por un alumno (evaluacion_id, alumno_id, fecha_hora, estado: Activa|Cancelada).
- **`ResultadoEvaluacion`**: nota final de un alumno en una evaluación (evaluacion_id, alumno_id, nota_final).

### Funcionalidades

- **F7.1 — Panel de métricas**: `GET /api/coloquios/metricas` — total alumnos cargados, instancias activas, reservas activas, notas registradas. Solo COORDINADOR/ADMIN.
- **F7.2 — Importar alumnos**: `POST /api/coloquios/{id}/alumnos` — carga lista de alumnos habilitados para una convocatoria. Crea `ResultadoEvaluacion` con nota_final=NULL como placeholder. Guard: `coloquios:gestionar`.
- **F7.3 — Crear convocatoria**: `POST /api/coloquios` — crea `Evaluacion` con materia, cohorte, tipo, instancia, días_disponibles. Guard: `coloquios:gestionar`.
- **F7.4 — Listado de convocatorias**: `GET /api/coloquios` — tabla con métricas derivadas (convocados, reservas activas, cupos libres). Guard: `coloquios:ver`.
- **F7.5 — Admin global**: endpoints para COORDINADOR/ADMIN:
  - `GET /api/coloquios/agenda` — reservas activas consolidadas.
  - `GET /api/coloquios/registro` — notas finales consolidadas.
  - `PATCH /api/coloquios/{id}` — cerrar convocatoria (no más reservas).
  - `PATCH /api/coloquios/resultados/{id}` — registrar nota final de un alumno.

### Flujo ALUMNO (FL-07)
- `GET /api/coloquios/disponibles` — convocatorias activas donde el alumno está habilitado.
- `POST /api/coloquios/{id}/reservar` — reserva turno (elige fecha_hora). Resta cupo. Si no hay cupo → 409.
- `GET /api/coloquios/mis-reservas` — historial de reservas del alumno.
- `DELETE /api/coloquios/reservas/{id}` — cancela reserva (libera cupo).

### Transversal
- **Permisos nuevos**: `coloquios:gestionar` (crear/modificar convocatorias, importar alumnos, registrar notas), `coloquios:ver` (consultar listados, métricas, agenda, registro). Se seedean en migration.
- **Migración 012**: tablas `evaluacion`, `reserva_evaluacion`, `resultado_evaluacion`.
- **Audit**: acciones `COLOQUIO_CREAR`, `COLOQUIO_CERRAR`, `ALUMNO_IMPORTAR`, `RESERVA_CREAR`, `RESERVA_CANCELAR`, `NOTA_REGISTRAR`.

## Capabilities

### New Capabilities
- `coloquios`: Gestión completa del ciclo de coloquios — convocatoria con cupos, importación de alumnos habilitados, reserva de turno por ALUMNO (FL-07), registro de notas finales, panel de métricas, agenda consolidada, registro académico.

### Modified Capabilities
None — módulo completamente nuevo.

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/evaluacion.py` | New | Modelo `Evaluacion` — convocatoria de coloquio |
| `backend/app/models/reserva_evaluacion.py` | New | Modelo `ReservaEvaluacion` — turno reservado por ALUMNO |
| `backend/app/models/resultado_evaluacion.py` | New | Modelo `ResultadoEvaluacion` — nota final |
| `backend/app/repositories/coloquio_repository.py` | New | Repos para Evaluacion + ReservaEvaluacion + ResultadoEvaluacion |
| `backend/app/schemas/coloquios.py` | New | Pydantic DTOs |
| `backend/app/services/coloquio_service.py` | New | Lógica de convocatorias, reservas (cupo), notas, métricas |
| `backend/app/api/v1/routers/coloquios.py` | New | Endpoints /api/coloquios/* |
| `backend/app/main.py` | Modified | Registrar router |
| `backend/alembic/versions/012_coloquios.py` | New | Migración 012: 3 tablas + seed permisos |
