# Proposal: Frontend Academico Docente (C-22)

## Intent

Interfaz del PROFESOR: importar calificaciones, ver atrasados, enviar comunicaciones, consultar reportes. Consume C-10, C-11, C-12.

## Scope

### In Scope
- `features/calificaciones/` — importar con preview, tabla de notas, configurar umbral
- `features/atrasados/` — tabla con filtros, ranking, detalle por alumno
- `features/comunicaciones/` — preview de mensaje, envío, tracking de estado
- TanStack Query para fetching/caching. React Hook Form + Zod para forms.

### Out of Scope
- Features de coordinador (C-23)
- Gráficos avanzados

## Capabilities
### New
- `frontend-docente`: Páginas del perfil PROFESOR/TUTOR

### Modified
None

## Approach
Feature-based: `features/{domain}/{pages,components,hooks,services}`. Hooks usan TanStack Query contra endpoints del backend.

## Dependencies
C-21 ✅, C-10 ✅, C-11 ✅, C-12 ✅

## Success Criteria
- [ ] 3 features con pages + hooks
- [ ] Tests con vitest para hooks y componentes clave
- [ ] ≥8 tests
