## Context

C-06 es el primer change del dominio académico. Establece las entidades raíz sobre las que se construyen todos los módulos siguientes: calificaciones, equipos docentes, encuentros, coloquios, padrón de alumnos, comunicaciones.

El stack actual ya tiene: FastAPI skeleton, multi-tenancy row-level, RBAC con `require_permission()`, JWT auth, audit log append-only, y repositorios base con tenant isolation. C-06 se apoya en todo eso.

**ADR-006** (ya cerrado) separa `Materia` (catálogo único del tenant) de `Dictado` (instancia de materia en una `carrera × cohorte` concreta). Este change implementa ambos.

## Goals / Non-Goals

**Goals:**
- Modelos Carrera, Cohorte, Materia, Dictado con herencia de `TenantScopedMixin` + `SoftDeleteMixin`.
- ABM completo para cada entidad vía endpoints REST bajo `/api/admin/`.
- Guard `estructura:gestionar` en todos los endpoints de administración.
- Reglas de unicidad y estado activa/inactiva según E1-E3 de la KB.
- Aislamiento multi-tenant: cada tenant ve solo sus carreras/cohortes/materias/dictados.

**Non-Goals:**
- CRUD de asignaciones (C-07), equipos docentes (C-08), calificaciones (C-10) — dependen de estas entidades pero son changes separados.
- Programa de materias (documentos PDF) — F5.3, change separado.
- Fechas de evaluaciones — F5.4, change separado.
- Endpoints públicos para alumnos — el frontend de alumnos es C-21+.

## Decisions

### D1. Dictado como entidad separada
Incluir `Dictado` en C-06 en lugar de aplazarlo. ADR-006 ya es decisión cerrada, y `Dictado` es necesario para C-08 (equipos docentes), C-10 (calificaciones), C-13 (encuentros). Separarlo ahora evita tener que modificar los modelos de C-06 después.

**Alternativa considerada**: agregar `carrera_id` y `cohorte_id` directamente en `Materia`. Rechazada porque una misma materia se dicta en múltiples carreras/cohortes (ej: "Programación I" se da en TUPAD y TUSI).

### D2. Soft-delete en todas las entidades
Carrera, Cohorte, Materia y Dictado heredan `SoftDeleteMixin`. Aunque el dominio hable de "inactiva" como estado de negocio, el soft-delete es necesario para integridad referencial: una carrera "eliminada" no debe romper referencias históricas en calificaciones o asignaciones.

**Trade-off**: el soft-delete convive con el campo `estado` (activa/inactiva). Un registro soft-deleteado se considera eliminado; uno con `estado=inactiva` está pausado pero visible.

### D3. Endpoints planos por entidad (no anidados)
Rutas tipo `/api/admin/carreras/{id}/cohortes` **no** se incluyen por ahora. Los endpoints son planos:
- `GET/POST /api/admin/carreras`, `GET/PUT /api/admin/carreras/{id}`
- `GET/POST /api/admin/cohortes`, `GET/PUT /api/admin/cohortes/{id}`
- etc.

El filtrado por carrera en cohortes se hace vía query param (ej: `GET /api/admin/cohortes?carrera_id=...`). Esto mantiene los routers simples y consistentes. Si se necesita una jerarquía más rica, se agrega en un change posterior.

**Alternativa considerada**: rutas anidadas tipo `/api/admin/carreras/{id}/cohortes`. Rechazada porque agrega complejidad de routing sin beneficio claro para el MVP, y porque entorpece la paginación y el filtrado.

### D4. Repositorio genérico para CRUD simple
Las cuatro entidades tienen CRUD prácticamente idéntico (create, get, update, list, soft-delete). Usar `BaseRepository` directamente sin wrappers específicos a menos que se necesite lógica adicional. Si alguna entidad requiere lógica extra (ej: validación de carrera activa antes de crear cohorte), se agrega un método en el service.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| PA-01: estructura de materias no completamente resuelta | ADR-006 ya cerró Materia+Dictado. Si PA-01 revela cambios, se resuelven en C-06 sin afectar otras entidades. |
| PA-07: cohortes transversales vs por carrera | Asumimos Cohorte → Carrera (como está en E2). Si PA-07 resuelve transversalidad, se agrega una tabla puente en change posterior. |
| Migración 005 choca con migración 004 de C-05 | Verificar que `down_revision` de 005 apunte a `"004"` (la de audit-log). |
| Dictado aumenta el scope de C-06 (~25%) | Es necesario para evitar modificar modelos después. El ABM de Dictado es idéntico al de las otras entidades — no agrega complejidad técnica nueva. |
