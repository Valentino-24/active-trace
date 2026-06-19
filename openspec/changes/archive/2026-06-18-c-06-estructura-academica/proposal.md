## Why

C-06 es la base de todo el dominio académico. Sin Carrera, Cohorte, Materia (catálogo) y Dictado (instancia), ningún módulo subsiguiente puede operar: calificaciones, equipos docentes, encuentros, coloquios, padrón de alumnos. ADR-006 ya estableció que `Materia` es el catálogo único del tenant y `Dictado` la instancia en una `carrera × cohorte` concreta; este change materializa esa decisión.

## What Changes

- **Modelos nuevos**: `Carrera`, `Cohorte`, `Materia` (catálogo), `Dictado` (instancia de materia en carrera × cohorte).
- **Endpoints ABM** bajo `/api/admin/` con guard `estructura:gestionar`:
  - `Carreras`: alta, edición, cambio de estado (activa/inactiva).
  - `Cohortes`: alta, edición, cambio de estado, vinculadas a una carrera.
  - `Materias`: alta, edición, cambio de estado (catálogo del tenant).
  - `Dictados`: alta, edición, cierre, vinculan materia + carrera + cohorte.
- **Reglas de negocio**:
  - Unicidad `(tenant_id, codigo)` en Carrera y Materia.
  - Unicidad `(tenant_id, carrera_id, nombre)` en Cohorte.
  - Carrera inactiva no admite cohortes activas.
  - Dictado requiere materia, carrera y cohorte activos.
- **Migración 005**: tablas `carrera`, `cohorte`, `materia`, `dictado`.
- **Tests**: CRUD + unicidad por tenant + aislamiento multi-tenant + reglas de estado activa/inactiva.

## Capabilities

### New Capabilities
- `carreras`: Administración de carreras (ABM + estado activa/inactiva).
- `cohortes`: Administración de cohortes vinculadas a una carrera (ABM + vigencia).
- `materias`: Catálogo único de materias del tenant (ABM + estado activa/inactiva).
- `dictados`: Instancias de dictado de una materia en una carrera × cohorte (ABM + cierre).

### Modified Capabilities
<!-- No existing specs to modify — main specs were just created from C-01 and C-05 archives. -->

## Impact

- **Modelos nuevos**: `Carrera`, `Cohorte`, `Materia`, `Dictado` en `app/models/`.
- **Repositorios nuevos**: `CarreraRepository`, `CohorteRepository`, `MateriaRepository`, `DictadoRepository` en `app/repositories/`.
- **Routers nuevos**: `admin/carreras.py`, `admin/cohortes.py`, `admin/materias.py`, `admin/dictados.py` bajo `app/api/v1/routers/`.
- **Migración**: `005_crear_estructura_academica.py`.
- **Permisos**: `estructura:gestionar` ya existe desde C-04; no requiere seed adicional.
- **Tests**: ~40 tests nuevos (CRUD + reglas + aislamiento).
