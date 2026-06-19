# Tasks: c-11-analisis-atrasados-reportes

> Governance: MEDIO — implementar con checkpoints, surfacear decisiones no obvias.
> Todos los endpoints son read-only sobre `Calificacion`, `UmbralMateria` y `EntradaPadron`. No requiere migraciones ni nuevos modelos.
> **Scope**: PROFESOR/TUTOR ve solo alumnos de su propia asignación (vía `_get_profesor_asignacion_ids()`). COORDINADOR/ADMIN ve scope global.

## 1. Schemas Pydantic (`schemas/analisis.py`)

- [x] 1.1 Crear `schemas/analisis.py` con `extra='forbid'` y `from_attributes=True` donde corresponda:
  - `AtrasadoRow` — `entrada_padron_id: UUID`, `alumno: str` ("Apellidos, Nombre"), `actividades_faltantes: list[str]`, `actividades_desaprobadas: list[str]`, `total_atrasos: int`, `avance_pct: float`
  - `AtrasadosResponse` — `items: list[AtrasadoRow]`, `total: int`
  - `RankingRow` — `posicion: int`, `entrada_padron_id: UUID`, `alumno: str`, `actividades_aprobadas: int`, `total_actividades: int`, `porcentaje_aprobacion: float`
  - `RankingResponse` — `items: list[RankingRow]`, `total_actividades: int`, `total_alumnos: int`
  - `ReporteRapidoResponse` — `total_alumnos: int`, `alumnos_atrasados: int`, `actividades_sin_corregir: int`, `porcentaje_aprobacion_general: float`, `estado: str` ("con_datos" | "sin_datos")
  - `ActividadNota` — `nombre: str`, `nota: Decimal | None`, `nota_textual: str | None`, `aprobado: bool`
  - `NotasFinalesRow` — `entrada_padron_id: UUID`, `alumno: str`, `promedio: float | None`, `aprobado: bool`, `umbral_aplicado: float`, `actividades: list[ActividadNota]`
  - `NotasFinalesResponse` — `items: list[NotasFinalesRow]`
  - `SinCorregirRow` — `alumno: str`, `actividad: str`, `fecha_entrega: date | None`
  - `MonitorGeneralRow` — `entrada_padron_id: UUID`, `alumno: str`, `estado: str` ("al_dia" | "atrasado" | "sin_datos"), `actividades_aprobadas: int`, `total_actividades: int`, `porcentaje_avance: float | None`
  - `MonitorGeneralResponse` — `items: list[MonitorGeneralRow]`, `total: int`
  - `MonitorSeguimientoRow` — `entrada_padron_id: UUID`, `alumno: str`, `actividad_nombre: str`, `nota: Decimal | None`, `nota_textual: str | None`, `resultado: str` ("aprobado" | "desaprobado"), `estado_general: str` ("al_dia" | "atrasado" | "sin_datos")
  - `MonitorSeguimientoResponse` — `items: list[MonitorSeguimientoRow]`, `total: int`

- [x] 1.2 Exportar schemas desde `app.schemas.analisis` (import en router/service)

## 2. Repositorio (`repositories/analisis_repository.py`)

- [x] 2.1 Crear `AnalisisRepository` **sin** heredar de `BaseRepository` (queries cross-model con `self._session.execute()` directo y filtros tenant manuales):
  - `__init__(self, db: AsyncSession, tenant_id: UUID)`
  - `list_actividades(materia_id, cohorte_id)` → `list[str]` — DISTINCT `actividad_nombre` de `Calificacion` para una materia+cohorte (determina actividades disponibles)
  - `list_alumnos_con_calificaciones(materia_id, cohorte_id, asignacion_ids opcional)` → rows join `EntradaPadron` + `Calificacion` con todos los campos necesarios para computar atrasados, ranking y notas
  - `count_aprobados_por_actividad(materia_id, cohorte_id, asignacion_ids opcional)` → `list[tuple[str, int, int]]` — por cada `actividad_nombre`, total alumnos y aprobados (para ranking F2.3)
  - `find_missing_activities(materia_id, cohorte_id, asignacion_ids opcional)` → `list[tuple[UUID, str, str]]` — LEFT JOIN entre `EntradaPadron` y `Calificacion` donde `c.id IS NULL` (actividades faltantes)
  - `list_sin_corregir(materia_id, cohorte_id, asignacion_ids opcional)` → `list[tuple[str, str, date | None]]` — actividades textuales (RN-02) con finalización registrada pero sin calificación (RN-07/08)
  - `monitor_query(materia_id opcional, comision opcional, regional opcional, q opcional, skip, limit)` → paginated rows con filtros dinámicos (F2.7), scope siempre global (COORD/ADMIN only)
  - `monitor_seguimiento_query(materia_id opcional, alumno_id opcional, asignacion_ids opcional, desde opcional, hasta opcional)` → detalle por alumno+actividad (F2.8/F2.9)
  - ⚠️ **Checkpoint**: Todas las queries deben incluir `tenant_id` explícito (no hay `_stmt()` heredado). Verificar consistencia con el patrón de soft delete (`deleted_at IS NULL`).
  - ⚠️ **Checkpoint**: El filtro dinámico en `monitor_query` (comision, regional, q) requiere construir WHERE clauses condicionales. Evaluar entre `and_()` con condiciones opcionales vs string concatenation SQL.

- [x] 2.2 Exportar `AnalisisRepository` en `repositories/__init__.py`

## 3. Servicio (`services/analisis_service.py`)

- [x] 3.1 Funciones puras (trivialmente testeables, sin DB):
  - `es_atrasado(total_actividades: int, aprobadas: int, faltantes: int)` → `bool` — True si faltantes > 0 o aprobadas < total (RN-06)
  - `compute_ranking(alumnos: list[dict])` → `list[dict]` — ordena descendente por aprobadas, asigna posición manejando empates (misma posición si mismo count)
  - `compute_nota_final(notas: list[Decimal | None], umbral_pct: float)` → `tuple[float | None, bool]` — promedio simple ignorando None, compara contra umbral
  - `compute_avance_pct(aprobadas: int, total: int)` → `float` — (aprobadas / total) × 100, maneja total=0 → 0.0

- [x] 3.2 Crear `AnalisisService` con dependencias `(db, tenant_id)`:
  - `listar_atrasados(materia_id, cohorte_id, asignacion_ids opcional)` → `AtrasadosResponse`:
    - Obtener actividades disponibles vía repo
    - Obtener alumnos con calificaciones vía repo
    - Para cada alumno: calcular faltantes (actividades sin registro), desaprobadas (`aprobado=false`), avance_pct
    - Filtrar solo alumnos con atraso (faltantes > 0 o desaprobadas > 0)
    - Excluir alumnos sin ninguna calificación registrada (spec: "sin datos no se puede determinar atraso")
  - `get_ranking(materia_id, cohorte_id, asignacion_ids opcional)` → `RankingResponse`:
    - Obtener conteo de aprobados por actividad vía repo
    - Para cada alumno: contar actividades aprobadas, calcular porcentaje
    - Excluir alumnos con 0 aprobadas (RN-09)
    - Ordenar descendente por aprobadas, asignar posición
  - `get_reportes_rapidos(materia_id, cohorte_id, asignacion_ids opcional)` → `ReporteRapidoResponse`:
    - Total alumnos inscriptos en padrón activo
    - Atrasados usando misma lógica que listar_atrasados
    - Sin corregir vía repo.list_sin_corregir
    - Porcentaje de aprobación general
    - Estado "sin_datos" si no hay calificaciones
  - `get_notas_finales(materia_id, cohorte_id, asignacion_ids opcional)` → `NotasFinalesResponse`:
    - Para cada alumno con notas numéricas: promedio simple
    - Incluir desglose por actividad
    - Ignorar actividades textuales para promedio numérico
    - Aprobar/reprobar contra umbral efectivo (RN-03 → UmbralMateria, fallback 60%)
    - Alumnos sin notas numéricas: promedio null, aprobado según regla textual
  - `exportar_sin_corregir(materia_id, cohorte_id, asignacion_ids opcional)` → `StreamingResponse` con CSV:
    - Usar `csv.writer` + `io.StringIO` con BOM para Excel
    - Columnas: "Alumno", "Actividad", "Fecha de Entrega"
    - Filtrar solo actividades textuales (RN-08)
    - Content-Type: `text/csv`, Content-Disposition: `attachment; filename="sin_corregir.csv"`
  - `monitor_general(materia_id opcional, comision opcional, regional opcional, q opcional, skip, limit)` → `MonitorGeneralResponse`:
    - Scope: solo COORD/ADMIN (validado en router, no en service)
    - Filtros dinámicos: materia, comisión, regional, búsqueda textual
    - Para cada alumno: estado general (al_dia=100% aprobadas, atrasado=<100%, sin_datos=sin calificaciones)
  - `monitor_seguimiento(materia_id opcional, alumno_id opcional, asignacion_ids opcional, desde opcional, hasta opcional)` → `MonitorSeguimientoResponse`:
    - Scope: PROFESOR/TUTOR ve asignaciones propias, COORD/ADMIN ve todas + filtro fechas
    - Para cada alumno: detalle por actividad con nota, resultado, estado_general
    - PROFESOR/TUTOR: ignorar params `desde`/`hasta` sin error (spec R-ANA-08)

- [x] 3.3 Exportar `AnalisisService` en `services/__init__.py`

## 4. Router (`api/v1/routers/analisis.py`)

- [x] 4.1 Crear `api/v1/routers/analisis.py` con `APIRouter(tags=["analisis"])` y dependencia global `require_permission("atrasados:ver")`:
  - `GET /api/analisis/atrasados?materia_id=&cohorte_id=` → `AtrasadosResponse` (F2.2)
    - Scope: `_get_profesor_asignacion_ids()` (reusar helper de C-10) limitando si PROFESOR/TUTOR
  - `GET /api/analisis/ranking?materia_id=&cohorte_id=` → `RankingResponse` (F2.3)
    - Mismo scope pattern
  - `GET /api/analisis/reportes-rapidos?materia_id=&cohorte_id=` → `ReporteRapidoResponse` (F2.4)
    - Mismo scope pattern
  - `GET /api/analisis/notas-finales?materia_id=&cohorte_id=` → `NotasFinalesResponse` (F2.5)
    - Mismo scope pattern
  - `GET /api/analisis/exportar-sin-corregir?materia_id=&cohorte_id=` → `StreamingResponse` (F2.6, CSV)
    - Content-Disposition attachment, media_type text/csv
  - `GET /api/analisis/monitor-general?materia_id=&comision=&regional=&q=&skip=0&limit=20` → `MonitorGeneralResponse` (F2.7)
    - ⚠️ **Checkpoint**: PROFESOR no tiene acceso (403). Solo COORD/ADMIN. Verificar con `require_permission` + role check inline.
  - `GET /api/analisis/monitor-seguimiento?materia_id=&alumno_id=&desde=&hasta=` → `MonitorSeguimientoResponse` (F2.8/F2.9)
    - Scope dinámico: PROFESOR/TUTOR limitado a asignaciones propias, ignora desde/hasta
    - COORD/ADMIN: scope global, aplica filtros desde/hasta
    - Validar que desde ≤ hasta (si ambos presentes) → 422 si no

- [x] 4.2 Extraer helper `_get_profesor_asignacion_ids` a un módulo compartido o duplicarlo localmente en el router (ya existe en calificaciones.py):
  - ⚠️ **Checkpoint**: Decidir si refactorizar a `app.core.permissions` o mantener duplicado. Si se refactoriza, impacta C-10 también. Preferir duplicación local para no modificar código existente, a menos que el refactor sea trivial.

## 5. Registrar router en main.py

- [x] 5.1 Agregar import y `include_router(analisis_router, prefix="/api/analisis")` en `main.py`
  - Import: `from app.api.v1.routers.analisis import router as analisis_router`
  - Registro: `app.include_router(analisis_router, prefix="/api/analisis")`
  - Verificar que no haya conflicto con otros prefixes

## 6. Tests

- [x] 6.1 Tests unitarios de funciones puras (sin DB, parametrized):
  - `es_atrasado`:
    - faltantes=0, aprobadas=total → False (al día)
    - faltantes>0 → True (atrasado por faltante)
    - aprobadas<total, faltantes=0 → True (atrasado por desaprobada)
  - `compute_ranking`:
    - Orden descendente por aprobadas
    - Empates comparten posición
    - Lista vacía → lista vacía
  - `compute_nota_final`:
    - Promedio simple de [85, 90, 70] → (81.67, true contra 60%)
    - Promedio [45, 50, 55] → (50.0, false contra 60%)
    - Lista vacía → (None, false)
    - Con None intercalados → ignora None para promedio numérico
  - `compute_avance_pct`:
    - 3/5 → 60.0
    - 0/5 → 0.0
    - 0/0 → 0.0

- [x] 6.2 Tests de integración: `GET /api/analisis/atrasados`:
  - Alumno con actividad faltante aparece como atrasado
  - Alumno con nota desaprobada aparece como atrasado
  - Alumno al día NO aparece
  - Alumno sin calificaciones NO aparece (sin datos)
  - Respuesta incluye avance_pct correcto
  - PROFESOR solo ve alumnos de su asignación
  - PROFESOR sin asignación en la materia → 403
  - COORDINADOR ve todas las asignaciones
  - Sin filtro de materia_id → 422 (required)

- [x] 6.3 Tests de integración: `GET /api/analisis/ranking`:
  - Ranking descendente por aprobadas
  - Excluye alumnos sin actividad aprobada (RN-09)
  - Empates en misma posición
  - PROFESOR solo ve su asignación
  - Response incluye metadata totales

- [x] 6.4 Tests de integración: `GET /api/analisis/reportes-rapidos`:
  - Reporte completo con métricas
  - Materia sin datos → estado "sin_datos"
  - Solo actividades textuales cuentan para sin_corregir (RN-08)

- [x] 6.5 Tests de integración: `GET /api/analisis/notas-finales`:
  - Promedio simple con indicador aprobado/reprobado
  - Alumno sin notas numéricas → promedio null
  - PROFESOR solo ve su asignación
  - Incluye desglose por actividad

- [x] 6.6 Tests de integración: `GET /api/analisis/exportar-sin-corregir`:
  - Exportación exitosa con datos → CSV con filas + cabecera
  - Excluye actividades numéricas (RN-08)
  - Sin TPs sin corregir → solo cabecera
  - Content-Type text/csv, Content-Disposition attachment
  - PROFESOR solo exporta su asignación

- [x] 6.7 Tests de integración: `GET /api/analisis/monitor-general`:
  - Sin filtros → todos los alumnos del tenant paginados
  - Filtro por materia_id
  - Filtro por comisión
  - Filtro por regional
  - Búsqueda textual por q (case-insensitive)
  - Estado "sin_datos" para alumno sin calificaciones
  - PROFESOR → 403 Forbidden
  - ADMIN → 200 (misma vista que COORD)

- [x] 6.8 Tests de integración: `GET /api/analisis/monitor-seguimiento`:
  - TUTOR consulta seguimiento de su materia
  - Filtro por alumno específico
  - PROFESOR no ve alumnos de otra asignación
  - TUTOR con múltiples asignaciones ve todas
  - Incluye estado_general por alumno
  - COORDINADOR ve seguimiento global (todas las asignaciones)
  - Filtro por rango de fechas (desde/hasta) para COORD/ADMIN
  - PROFESOR: params desde/hasta ignorados sin error
  - Rango inválido (desde > hasta) → 422 con mensaje

- [x] 6.9 Test de multi-tenancy y auth:
  - Datos de tenant A no visibles desde tenant B en todos los endpoints
  - Usuario sin `atrasados:ver` → 403
  - Token inválido → 401

## 7. Verificación

- [x] 7.1 Verificar que todos los tests pasan (pytest)
- [x] 7.2 Verificar cobertura ≥80% líneas, ≥90% reglas de negocio
- [x] 7.3 Verificar que cada archivo nuevo respeta ≤500 LOC (analisis.py router y service pueden estar cerca del límite — evaluar split si supera)
- [x] 7.4 Verificar que los schemas tienen `extra='forbid'`
- [x] 7.5 Verificar que no hay lógica de negocio en routers ni acceso directo a DB desde services
- [x] 7.6 Verificar que el permiso `atrasados:ver` está seedeado (fuera de scope de C-11, pero debe existir en tenant setup — confirmar)
