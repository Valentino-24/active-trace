# Proposal: Programas y Fechas Academicas

## Intent

Centralizar los programas oficiales de materia y el calendario de evaluaciones por carrera × cohorte. Hoy no existe una fuente única: cada docente administra sus fechas y programas en silos. Esto unifica la consulta y permite generar contenido para el LMS.

## Scope

### In Scope
- Modelo `ProgramaMateria`: asociar documento (referencia_archivo) a materia × carrera × cohorte
- Modelo `FechaAcademica`: parciales, TP, coloquios y recuperatorios por materia × cohorte
- Endpoints CRUD: `/api/programas`, `/api/fechas-academicas` con guard `estructura:gestionar`
- Listado tabular + filtros (materia, cohorte, tipo, periodo)
- Migración 015 con 2 tablas, FKs e índices

### Out of Scope
- Upload de archivos real (solo referencia opaca por ahora)
- Calendario visual (frontend)
- Generación de fragmento LMS (F5.4 salida — se aborda en C-22 frontend)
- Integración con encuentros (F6.4)

## Capabilities

### New Capabilities
- `programas`: CRUD de programas de materia con referencia de archivo opaca
- `fechas-academicas`: CRUD de fechas evaluativas con filtros por materia, cohorte, tipo y periodo

### Modified Capabilities
None — ambos dominios son nuevos, no modifican specs existentes.

## Approach

Dos modelos simples con FK a Materia, Carrera y Cohorte. Reutilizan `estructura:gestionar` (ya existe desde C-06). Repos CRUD estándar con `BaseRepository`. Endpoints REST convencionales.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/models/programa_materia.py` | New | ProgramaMateria |
| `backend/app/models/fecha_academica.py` | New | FechaAcademica + TipoFecha enum |
| `backend/app/models/__init__.py` | Modified | Export |
| `backend/app/repositories/programa_repository.py` | New | CRUD |
| `backend/app/repositories/fecha_repository.py` | New | CRUD + filtros |
| `backend/app/repositories/__init__.py` | Modified | Export |
| `backend/app/schemas/programas_fechas.py` | New | DTOs |
| `backend/app/services/programa_fecha_service.py` | New | Lógica |
| `backend/app/api/v1/routers/programas_fechas.py` | New | Endpoints |
| `backend/app/main.py` | Modified | Register router |
| `backend/alembic/versions/015_programas_fechas.py` | New | Migration |
| `backend/tests/test_programas_fechas.py` | New | Tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Archivos reales vs referencia opaca genera confusión | Med | Documentar que MVP solo guarda path/referencia |
| TipoFecha enum puede necesitar ampliación | Bajo | Dejar abierto a extensión sin migración |

## Rollback Plan

`alembic downgrade 014` revierte las tablas. Eliminar archivos creados. Revertir `__init__.py` y `main.py`.

## Dependencies

- C-06 estructura-academica (Materia, Carrera, Cohorte ya existen)

## Success Criteria

- [ ] 2 modelos con FK a materia, carrera, cohorte
- [ ] 6 endpoints CRUD (3 programas + 3 fechas)
- [ ] Filtros: materia_id, cohorte_id, tipo, periodo en fechas
- [ ] Migración 015 con seed (sin nuevo permiso — reusa `estructura:gestionar`)
- [ ] ≥20 tests entre unitarios, integración y E2E
- [ ] LOC ≤500 por archivo nuevo
