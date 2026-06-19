# Tasks: c-10-calificaciones-y-umbral

> Governance: MEDIO — implementar con checkpoints, surfacear decisiones no obvias.
> Docente que importa calificaciones SOLO ve/modifica datos de su propia asignación (RN-03). COORDINADOR/ADMIN ven todo.

## 1. Migración de base de datos (009)

- [ ] 1.1 Crear `009_calificacion_umbral.py` — tabla `calificacion`:
  - `id` UUID PK, `tenant_id` FK CASCADE (TenantScopedMixin), `entrada_padron_id` FK CASCADE → `entrada_padron.id`
  - `materia_id` FK CASCADE, `cohorte_id` FK CASCADE, `asignacion_id` FK CASCADE
  - `usuario_id` FK SET NULL → `users.id` (denormalizado para queries sin JOIN)
  - `actividad_nombre` String(255) NOT NULL, `nota` Decimal(6,2) nullable, `nota_textual` String(100) nullable
  - `aprobado` Boolean NOT NULL, `origen` String(20) NOT NULL (CHECK: `'Importado'` o `'Manual'`)
  - `metadata` JSONB nullable (max_nota por actividad, etc.), `periodo` String(20) NOT NULL
  - `created_at`, `updated_at`, `deleted_at` (SoftDeleteMixin)
  - Índice compuesto: `ix_calificacion_materia_cohorte` sobre `(materia_id, cohorte_id)`
  - Índice compuesto: `ix_calificacion_asignacion` sobre `(asignacion_id)`

- [ ] 1.2 Crear tabla `umbral_materia`:
  - `id` UUID PK, `tenant_id` FK CASCADE (TenantScopedMixin)
  - `materia_id` FK CASCADE, `cohorte_id` FK CASCADE
  - `asignacion_id` FK SET NULL nullable (NULL = umbral default de materia)
  - `umbral_pct` Decimal(4,3) NOT NULL default `0.600`
  - `valores_aprobatorios` ARRAY(String(100)) nullable (ej: `["Satisfactorio", "Supera lo esperado"]`)
  - `created_at`, `updated_at`, `deleted_at` (SoftDeleteMixin)
  - UniqueConstraint sobre `(tenant_id, materia_id, cohorte_id, asignacion_id)` — un umbral por asignación
  - Índice compuesto: `ix_umbral_materia_materia_cohorte` sobre `(materia_id, cohorte_id)`

- [ ] 1.3 Seed: agregar permiso `calificaciones:ver` (no existe en 003) siguiendo el patrón de 008 (ON CONFLICT DO NOTHING, por tenant) y asignarlo a PROFESOR, COORDINADOR y ADMIN
  - ⚠️ **Checkpoint**: `calificaciones:importar` ya fue seedeado en migración 003 con asignación a PROFESOR, COORDINADOR y ADMIN. Verificar que cubre los roles necesarios y NO volver a insertarlo.

## 2. Modelos SQLAlchemy

- [ ] 2.1 Crear `models/calificacion.py` — `Calificacion(Base, TenantScopedMixin, SoftDeleteMixin)`:
  - Columnas: `entrada_padron_id`, `materia_id`, `cohorte_id`, `asignacion_id`, `usuario_id` (nullable FK → User)
  - `actividad_nombre`, `nota` (Decimal nullable), `nota_textual` (nullable), `aprobado`, `origen` (enum string), `metadata` (JSONB nullable), `periodo`
  - Relationship `entrada_padron` → EntradaPadron (lazy="selectin"), `usuario` → User (lazy="selectin")
  - `__table_args__` con índices según migración

- [ ] 2.2 Crear `models/umbral_materia.py` — `UmbralMateria(Base, TenantScopedMixin, SoftDeleteMixin)`:
  - Columnas: `materia_id`, `cohorte_id`, `asignacion_id` (nullable), `umbral_pct` (default 0.600), `valores_aprobatorios` (ARRAY(String) nullable) vía `ARRAY(String(100))` o `JSON` como fallback portable
  - ⚠️ **Checkpoint**: SQLAlchemy 2.0 async con ARRAY de PostgreSQL requiere `from sqlalchemy.dialects.postgresql import ARRAY`. Alternativa portable: columna JSON con validación Pydantic. Decidir según consistencia con el resto del proyecto.

- [ ] 2.3 Exportar `Calificacion` y `UmbralMateria` en `models/__init__.py`

## 3. Schemas Pydantic

- [ ] 3.1 Crear `schemas/calificacion.py` con `extra='forbid'`:
  - `CalificacionResponse` (id, entrada_padron_id, usuario_id, actividad_nombre, nota, nota_textual, aprobado, origen, metadata, periodo, created_at)
  - `CalificacionListResponse` (items: list[CalificacionResponse], total: int, skip: int, limit: int)
  - `PreviewColumn` (nombre: str, tipo: Literal["numerica", "textual"], max_nota: Decimal | None)
  - `PreviewRow` (fila: int, email: str, nombre: str, apellidos: str, valores: dict[str, Decimal | str | None])
  - `PreviewResponse` (columnas: list[PreviewColumn], filas: list[PreviewRow], errores: list[dict], total_filas: int)
  - `ImportRequest` (materia_id: UUID, cohorte_id: UUID, actividad_nombre: str, notas: list[dict] — cada uno con email, nota opcional, nota_textual opcional)
  - `ImportResponse` (importadas: int, aprobadas: int, reprobadas: int, errores: list[str])
  - `FinalizacionRow` (alumno: str, actividad: str, estado: Literal["Sin_corregir"])
  - `FinalizacionResponse` (items: list[FinalizacionRow], total: int)

- [ ] 3.2 Crear `schemas/umbral_materia.py` con `extra='forbid'`:
  - `UmbralResponse` (id, materia_id, cohorte_id, asignacion_id opcional, umbral_pct, valores_aprobatorios opcional, created_at, updated_at)
  - `UmbralUpdateRequest` (umbral_pct opcional, valores_aprobatorios opcional — al menos uno requerido)
  - `UmbralListResponse` (items: list[UmbralResponse])

## 4. Repositorios

- [ ] 4.1 Crear `repositories/calificacion_repository.py`:
  - Heredar de `BaseRepository[Calificacion]` con `_model_cls = Calificacion`
  - `bulk_create(session, calificaciones: list[Calificacion])` — INSERT many con flush
  - `list_by_filters(materia_id, cohorte_id, asignacion_id opcional, skip, limit)` — listado paginado con filtros, scope tenant implícito
  - `list_by_asignacion(asignacion_id, skip, limit)` — para scope PROFESOR
  - `count_by_filters(materia_id, cohorte_id)` — total para paginación
  - `find_by_entrada_padron_y_actividad(entrada_padron_id, actividad_nombre)` — existe calificación previa?
  - `detectar_sin_nota(cohorte_id, materia_id, actividad_nombre)` — TPs textuales sin nota (F1.2)

- [ ] 4.2 Crear `repositories/umbral_materia_repository.py`:
  - Heredar de `BaseRepository[UmbralMateria]` con `_model_cls = UmbralMateria`
  - `get_effective_umbral(asignacion_id, materia_id, cohorte_id)` → tupla `(umbral_pct, valores_aprobatorios)`:
     1. Buscar por `(tenant_id, materia_id, cohorte_id, asignacion_id)` — específico
     2. Si no existe, buscar por `(tenant_id, materia_id, cohorte_id, asignacion_id IS NULL)` — default de materia
     3. Si no existe, devolver `(0.600, None)` — default global
  - `upsert(tenant_id, materia_id, cohorte_id, asignacion_id, umbral_pct, valores_aprobatorios)` — ON CONFLICT UPDATE (unique sobre `tenant_id, materia_id, cohorte_id, asignacion_id`)
  - `list_by_filters(materia_id, cohorte_id)` — listar umbrales de una materia

## 5. Servicios

- [ ] 5.1 Crear `services/calificaciones.py`:
  - `parsear_archivo_lms(file: UploadFile)` → `PreviewResponse`:
    - Detectar formato: `.xlsx` (openpyxl) o `.csv` (csv module). Otros → 400.
    - Detectar columnas: sufijo `(Real)` → numérica (RN-01); resto → textual (RN-02)
    - Extraer `max_nota` de fila "Calificación máxima" si existe, fallback a 100
    - Parsear filas de alumnos (saltar filas de metadata/cálculos hasta encontrar un header)
  - `importar_calificaciones(tenant_id, usuario_id, request: ImportRequest, db)` → `ImportResponse`:
    - Match each email → EntradaPadron por `email_hash`
    - Resolver umbral efectivo vía `UmbralService.get_effective_umbral()`
    - Derivar `aprobado` con `calcular_aprobado()`
    - Bulk insert vía repositorio
    - Audit `CALIFICACIONES_IMPORTAR` con `{materia_id, cohorte_id, actividad_nombre, total_notas, aprobadas, reprobadas, modo: "archivo"}`
  - `calcular_aprobado(nota, nota_textual, umbral_pct, max_nota, valores_aprobatorios)` → `bool` (función pura, trivially testable):
    - Si `nota is not None`: `return nota >= umbral_pct * max_nota`
    - Si `nota_textual`: `return nota_textual in (valores_aprobatorios or [])`
    - Sino: `return False`
  - `importar_finalizacion(tenant_id, materia_id, cohorte_id, file, db)` → `FinalizacionResponse`:
    - Parsear archivo de finalización (mismo formato LMS)
    - Identificar actividades textuales (RN-02) donde LMS marca "entregado" pero no hay `Calificacion` registrada
    - Excluir actividades numéricas (RN-08)
    - ⚠️ **Checkpoint**: El formato exacto del archivo de finalización (F1.2) no está definido — puede ser el mismo archivo LMS de calificaciones (filas sin nota = sin corregir) o un reporte separado. Surfacear decisión de interpretación.

- [ ] 5.2 Crear `services/umbral.py`:
  - `get_effective_umbral(asignacion_id, materia_id, cohorte_id, tenant_id, db)` → delegar en repositorio + OC para test unitario
  - `update_umbral(umbral_id, data: UmbralUpdateRequest, usuario, db)`:
    - Cargar umbral existente
    - Scope check: si usuario es PROFESOR, verificar que `umbral.asignacion_id` esté en sus asignaciones. Si no → 403
    - Actualizar campos, commmit
    - No recalcular calificaciones existentes (post-MVP)

## 6. APIs / Routers

- [ ] 6.1 Crear `api/v1/routers/calificaciones.py` con prefijo `/api/calificaciones` y tag `"calificaciones"` y `/api/umbrales`:
  - `POST /api/calificaciones/preview` — protege con `calificaciones:importar`, recibe UploadFile + materia_id + cohorte_id como form, delega en service
  - `POST /api/calificaciones/import` — protege con `calificaciones:importar`, recibe `ImportRequest` JSON body, delega en service, registra audit
  - `POST /api/calificaciones/importar-finalizacion` — protege con `calificaciones:importar`, recibe UploadFile + materia_id + cohorte_id, delega en service
  - `GET /api/calificaciones?materia_id=&cohorte_id=&skip=0&limit=20` — protege con `calificaciones:ver`, scope PROFESOR (solo su asignación) vs COORD/ADMIN (todas)
  - `GET /api/umbrales?materia_id=&cohorte_id=` — protege con `calificaciones:ver`, mismo scope
  - `PUT /api/umbrales/{id}` — protege con `calificaciones:importar`, scope check en service

- [ ] 6.2 Registrar router en `api/v1/routers/__init__.py` o donde se monten los routers (verificar patrón existente)

## 7. Tests

- [ ] 7.1 Test unitario de `calcular_aprobado` con pytest parametrized (0 mocks):
  - Numérica ≥ umbral → true (ej: nota=85, umbral=0.60, max=100 → true)
  - Numérica < umbral → false (ej: 45 → false)
  - Textual en valores_aprobatorios → true
  - Textual no en valores_aprobatorios → false
  - Sin nota ni textual → false
  - Nil check: nota=None, nota_textual=None → false

- [ ] 7.2 Test unitario de column detection:
  - `TP1 (Real)` → tipo `"numerica"`, nombre limpio `"TP1"`
  - `TP2 (Cualitativo)` → tipo `"textual"`
  - Sin sufijo → tipo `"textual"`

- [ ] 7.3 Test unitario de umbral inheritance chain:
  - Específico por asignación → devuelve ese
  - Sin específico, con default de materia → devuelve default
  - Sin ninguno → devuelve (0.60, None)

- [ ] 7.4 Test de integración: `POST /api/calificaciones/preview`:
  - Preview exitoso con .xlsx de columnas mixtas
  - Preview con errores de parseo por fila
  - Archivo no soportado → 400
  - Usuario sin `calificaciones:importar` → 403

- [ ] 7.5 Test de integración: `POST /api/calificaciones/import`:
  - Import exitoso con aprobados derivados + audit `CALIFICACIONES_IMPORTAR` verificado en BD
  - Alumno no encontrado en padrón → 400, transacción abortada (0 calificaciones persistidas)
  - Nota numérica por debajo del umbral → aprobado=false
  - Nota textual no aprobatoria → aprobado=false
  - Sin nota ni textual → aprobado=false, origen="Importado"

- [ ] 7.6 Test de integración: `POST /api/calificaciones/importar-finalizacion`:
  - Detecta TPs textuales entregados sin nota (F1.2)
  - Excluye actividades numéricas del reporte (RN-08)

- [ ] 7.7 Test de integración: `GET /api/calificaciones`:
  - Listado filtrado por materia_id + cohorte_id con paginación
  - PROFESOR solo ve calificaciones de su propia asignación (scope test, mismo patrón C-09)
  - COORDINADOR ve todas las de la materia

- [ ] 7.8 Test de integración: umbral endpoints:
  - `GET /api/umbrales` con y sin umbrales configurados
  - `PUT /api/umbrales/{id}` actualiza umbral_pct
  - `PUT /api/umbrales/{id}` actualiza valores_aprobatorios
  - PROFESOR modificando umbral de otra asignación → 403

- [ ] 7.9 Test de multi-tenancy: datos de tenant A no visibles desde tenant B en todos los endpoints

## 8. Verificación

- [ ] 8.1 Verificar que `009_calificacion_umbral.py` corre sin errores (alembic upgrade head)
- [ ] 8.2 Verificar que todos los tests pasan (pytest)
- [ ] 8.3 Verificar cobertura ≥80% líneas, ≥90% reglas de negocio
- [ ] 8.4 Verificar que cada archivo nuevo respeta ≤500 LOC
- [ ] 8.5 Verificar que los schemas tienen `extra='forbid'`
- [ ] 8.6 Verificar que no hay lógica de negocio en routers ni acceso directo a DB desde services
