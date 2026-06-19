## Why

El modelo de asignaciones individuales (C-07) permite crear, listar y revocar asignaciones una a una. Para que un COORDINADOR pueda gestionar equipos docentes completos de forma eficiente —especialmente al inicio de cada cuatrimestre— necesita operaciones de alto nivel: ver el equipo como conjunto, asignar múltiples docentes en bloque, clonar equipos entre períodos, ajustar vigencias masivamente y exportar la composición del equipo.

## What Changes

- Nuevo router `/api/equipos` con endpoints de alto nivel sobre asignaciones:
  - `GET /api/equipos/mi-equipo` — vista del equipo del docente autenticado (sus materias, comisiones, roles, vigencia)
  - `GET /api/equipos` — gestión de todas las asignaciones del tenant con filtros avanzados (F4.3)
  - `POST /api/equipos/asignacion-masiva` — asigna múltiples docentes a una combinación materia×carrera×cohorte×rol con vigencia
  - `POST /api/equipos/clonar` — duplica asignaciones de un origen a un destino (RN-12)
  - `PATCH /api/equipos/vigencia` — modifica vigencia `desde`/`hasta` de todas las asignaciones de un equipo
  - `GET /api/equipos/exportar` — descarga CSV/XLSX con el detalle del equipo
- Nuevo permiso `equipos:gestionar` para operaciones masivas (COORDINADOR, ADMIN)
- Auditoría: cada operación masiva genera evento `ASIGNACION_MODIFICAR`
- Tests de clonado, asignación masiva, modificación de vigencia en bloque, exportación

## Capabilities

### New Capabilities
- `equipos`: endpoints de alto nivel para gestión de equipos docentes (mis-equipos, asignación masiva, clonar, vigencia, exportar). Guard `equipos:gestionar`.

### Modified Capabilities
- `asignaciones`: se agregan los escenarios de operaciones masivas (bulk create, clonación, modificación de vigencia en lote) como requisitos adicionales sobre el modelo de asignación existente.

## Impact

- **Models**: sin cambios (reutiliza `Asignacion` de C-07)
- **New router**: `backend/app/api/v1/routers/equipos.py`
- **Repository**: `AsignacionRepository` se extiende con métodos bulk: `bulk_create()`, `clone_equipo()`, `update_vigencia_masiva()`
- **Schemas**: nuevos DTOs para operaciones masivas (`AsignacionMasivaRequest`, `CloneEquipoRequest`, `VigenciaRequest`, `EquipoExportRow`)
- **Permissions**: nuevo permiso `equipos:gestionar` + seed
- **Dependencies**: `C-07` (ya está)
- **Governance**: ALTO — operaciones masivas sobre datos de usuarios
