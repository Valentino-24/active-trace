# Análisis

> Consultas analíticas y reportes sobre calificaciones — alumnos atrasados, ranking de actividades aprobadas, reportes rápidos por materia, notas finales agrupadas, exportación de TPs sin corregir, y monitores de seguimiento con filtros. Opera como capa de solo lectura sobre `Calificacion`, `UmbralMateria` y `EntradaPadron`; no requiere nuevos modelos ni migraciones.

## Permisos

| Permiso | Descripción | Asignado a |
|---------|-------------|-----------|
| `atrasados:ver` | Acceso a todos los endpoints de análisis | PROFESOR (scope propia asignación), TUTOR (scope propia asignación), COORDINADOR, ADMIN |

## ADDED Requirements

### R-ANA-01 — Listar alumnos atrasados (F2.2)

`GET /api/analisis/atrasados?materia_id=&cohorte_id=`

El sistema DEBE devolver los alumnos en situación de atraso para una materia y cohorte según RN-06: un alumno está atrasado si cumple AL MENOS UNA de: (a) tiene actividades sin entregar (no existe `Calificacion` para esa actividad × ese alumno), (b) tiene nota registrada inferior al umbral (`Calificacion.aprobado = False`). El cómputo DEBE considerar todas las actividades disponibles en las calificaciones importadas para esa materia+cohorte.

Cada alumno en la respuesta DEBE incluir: nombre, apellido, actividades faltantes (lista), actividades desaprobadas (lista), porcentaje de avance (actividades aprobadas / total actividades × 100).

#### Escenario: PROFESOR lista atrasados de su asignación

- WHEN un PROFESOR autenticado solicita GET /api/analisis/atrasados?materia_id=X&cohorte_id=Y
- THEN responde 200 con los alumnos atrasados de su propia asignación (excluye alumnos de otras asignaciones en la misma materia)

#### Escenario: COORDINADOR lista atrasados globales de una materia

- WHEN un COORDINADOR solicita GET /api/analisis/atrasados?materia_id=X&cohorte_id=Y
- THEN responde 200 con los alumnos atrasados de TODAS las asignaciones de esa materia y cohorte

#### Escenario: alumno con actividad faltante se considera atrasado

- GIVEN un alumno tiene `Calificacion.aprobado=true` para TP1 pero NO existe registro de `Calificacion` para TP2
- WHEN se computan atrasados para su materia
- THEN el alumno aparece con `actividades_faltantes: ["TP2"]` y `atrasado: true`

#### Escenario: alumno con nota desaprobada se considera atrasado

- GIVEN un alumno tiene `Calificacion.aprobado=false` para TP1 con nota `45.0` contra umbral `60%`
- WHEN se computan atrasados
- THEN el alumno aparece con `actividades_desaprobadas: [{actividad: "TP1", nota: 45.0}]` y `atrasado: true`

#### Escenario: alumno al día no aparece en la lista

- GIVEN un alumno tiene todas las actividades aprobadas
- WHEN se computan atrasados
- THEN el alumno NO aparece en la respuesta

#### Escenario: alumno sin calificaciones registradas no aparece

- GIVEN un alumno está en el padrón pero no tiene ningún registro `Calificacion` asociado
- WHEN se computan atrasados
- THEN el alumno NO aparece (sin datos no se puede determinar atraso)

#### Escenario: respuesta incluye porcentaje de avance

- GIVEN una materia con 5 actividades y un alumno con 3 aprobadas, 1 desaprobada y 1 faltante
- WHEN se computan atrasados
- THEN el registro del alumno incluye `avance_pct: 60.0`

#### Escenario: PROFESOR sin asignación en la materia

- GIVEN un PROFESOR sin asignación vigente en materia X
- WHEN solicita GET /api/analisis/atrasados?materia_id=X&cohorte_id=Y
- THEN responde 403 Forbidden

### R-ANA-02 — Ranking de actividades aprobadas (F2.3)

`GET /api/analisis/ranking?materia_id=&cohorte_id=`

El sistema DEBE devolver un ranking descendente por cantidad de actividades aprobadas. SOLO DEBE incluir alumnos con al menos una actividad aprobada (RN-09). Cada entrada DEBE incluir: posición, nombre del alumno, apellido, cantidad de actividades aprobadas, total de actividades, porcentaje de aprobación. Scope PROFESOR: su propia asignación. Scope COORD/ADMIN: global por materia.

#### Escenario: ranking descendente por aprobadas

- GIVEN alumno A con 4 aprobadas de 5, alumno B con 2 aprobadas de 5, alumno C con 1 aprobada de 5
- WHEN GET /api/analisis/ranking?materia_id=X&cohorte_id=Y
- THEN responde 200 con alumnos ordenados: A (posición 1), B (posición 2), C (posición 3)

#### Escenario: excluye alumnos sin actividad aprobada (RN-09)

- GIVEN alumno D con 0 actividades aprobadas (todas desaprobadas o faltantes)
- WHEN GET /api/analisis/ranking?materia_id=X&cohorte_id=Y
- THEN el alumno D NO aparece en el ranking

#### Escenario: empate en cantidad de aprobadas

- GIVEN alumnos A y B ambos con 3 actividades aprobadas
- WHEN GET /api/analisis/ranking
- THEN ambos aparecen en la misma posición (empate) o se desempata por porcentaje de aprobación

#### Escenario: PROFESOR solo ve alumnos de su asignación

- GIVEN un PROFESOR con asignación A en materia X, y existen alumnos en asignación B
- WHEN GET /api/analisis/ranking?materia_id=X&cohorte_id=Y
- THEN el ranking solo incluye alumnos de la asignación A

#### Escenario: respuesta incluye metadata de totales

- WHEN GET /api/analisis/ranking?materia_id=X&cohorte_id=Y
- THEN responde 200 con `items` (lista rankeada) y `total_actividades` (cantidad de actividades únicas en la materia)

### R-ANA-03 — Reportes rápidos por materia (F2.4)

`GET /api/analisis/reportes-rapidos?materia_id=&cohorte_id=`

El sistema DEBE devolver métricas resumen para una materia y cohorte específicas: total de alumnos inscriptos en el padrón activo, cantidad de alumnos atrasados (según RN-06), cantidad de actividades sin corregir (entregas textuales sin calificación — RN-07/08), y porcentaje de aprobación general (alumnos con todas las actividades aprobadas / total alumnos con datos × 100).

#### Escenario: reporte completo con métricas

- GIVEN materia X con 30 alumnos inscriptos, 8 atrasados, 3 TPs sin corregir, 15 alumnos con todas las actividades aprobadas
- WHEN GET /api/analisis/reportes-rapidos?materia_id=X&cohorte_id=Y
- THEN responde 200 con `total_alumnos: 30`, `alumnos_atrasados: 8`, `actividades_sin_corregir: 3`, `porcentaje_aprobacion_general: 50.0`

#### Escenario: materia sin datos importados

- GIVEN materia X sin calificaciones importadas
- WHEN GET /api/analisis/reportes-rapidos?materia_id=X&cohorte_id=Y
- THEN responde 200 con métricas en cero y un campo `estado: "sin_datos"`

#### Escenario: solo actividades textuales sin corregir (RN-08)

- GIVEN un TP numérico entregado sin nota y un TP textual entregado sin nota
- WHEN GET /api/analisis/reportes-rapidos
- THEN `actividades_sin_corregir` SOLO incluye el TP textual

### R-ANA-04 — Notas finales agrupadas (F2.5)

`GET /api/analisis/notas-finales?materia_id=&cohorte_id=`

El sistema DEBE calcular para cada alumno el promedio simple de todas las notas numéricas registradas, ignorando actividades textuales para el promedio numérico. DEBE incluir: nombre del alumno, apellido, promedio numérico, indicador de aprobado/reprobado contra el umbral efectivo (según RN-03: umbral específico → umbral de materia → 60%), y lista de notas individuales por actividad.

#### Escenario: promedio simple con indicador de aprobado

- GIVEN alumno con notas `[85.0, 90.0, 70.0]` y umbral efectivo `0.60` sobre `max_nota=100`
- WHEN GET /api/analisis/notas-finales?materia_id=X&cohorte_id=Y
- THEN responde con `promedio: 81.67`, `aprobado: true`, `umbral_aplicado: 0.60`

#### Escenario: promedio por debajo del umbral

- GIVEN alumno con notas `[45.0, 50.0, 55.0]` y umbral efectivo `0.60`
- WHEN GET /api/analisis/notas-finales
- THEN `promedio: 50.0`, `aprobado: false`

#### Escenario: alumno sin notas numéricas

- GIVEN un alumno con solo calificaciones textuales (sin nota numérica)
- WHEN GET /api/analisis/notas-finales
- THEN el alumno aparece con `promedio: null` y `aprobado` determinado por la regla textual

#### Escenario: PROFESOR solo ve notas de su asignación

- GIVEN un PROFESOR con asignación A
- WHEN GET /api/analisis/notas-finales?materia_id=X&cohorte_id=Y
- THEN solo devuelve notas de alumnos de la asignación A

#### Escenario: incluye desglose por actividad

- WHEN GET /api/analisis/notas-finales?materia_id=X&cohorte_id=Y
- THEN cada item de alumno incluye `actividades: [{nombre: "TP1", nota: 85.0, aprobado: true}, ...]`

### R-ANA-05 — Exportar TPs sin corregir (F2.6)

`GET /api/analisis/exportar-sin-corregir?materia_id=&cohorte_id=`

El sistema DEBE generar un archivo CSV descargable (con BOM para Excel) con el listado de trabajos prácticos textuales entregados (finalizados por el alumno según reporte LMS) pero sin calificación registrada. SOLO incluye actividades textuales (RN-08). Columnas del CSV: alumno (nombre y apellido), actividad, fecha de entrega (si está disponible). Scope PROFESOR: sus propias asignaciones. Scope COORD: todas las asignaciones de la materia.

#### Escenario: exportación exitosa con datos

- GIVEN 5 TPs textuales sin corregir para materia X
- WHEN GET /api/analisis/exportar-sin-corregir?materia_id=X&cohorte_id=Y
- THEN responde 200 con Content-Type text/csv, Content-Disposition attachment, y 5 filas de datos más cabecera

#### Escenario: excluye actividades numéricas (RN-08)

- GIVEN 3 TPs textuales sin corregir y 2 TPs numéricos sin nota registrada
- WHEN GET /api/analisis/exportar-sin-corregir
- THEN el CSV solo contiene las 3 filas de actividades textuales

#### Escenario: sin TPs sin corregir

- GIVEN todas las actividades textuales tienen calificación registrada
- WHEN GET /api/analisis/exportar-sin-corregir
- THEN responde 200 con CSV que solo contiene la fila de cabecera

#### Escenario: PROFESOR exporta de otra asignación

- GIVEN un PROFESOR con asignación A que intenta exportar de asignación B
- WHEN GET /api/analisis/exportar-sin-corregir?materia_id=X&cohorte_id=Y
- THEN responde 200 con datos limitados a su asignación A (no ve B)

### R-ANA-06 — Monitor general de actividades (F2.7)

`GET /api/analisis/monitor-general?materia_id=&comision=&regional=&q=`

El sistema DEBE devolver una vista transversal de todos los alumnos del tenant con filtros opcionales: materia_id, comisión, regional, búsqueda textual (por nombre o apellido). Visible solo para COORDINADOR y ADMIN. Columnas: alumno (nombre y apellido), estado general (`al_dia` / `atrasado` / `sin_datos`), actividades aprobadas, total actividades, porcentaje de avance. Responde con paginación.

#### Escenario: monitor general sin filtros

- WHEN un COORDINADOR solicita GET /api/analisis/monitor-general
- THEN responde 200 con todos los alumnos del tenant que tienen datos en alguna materia, paginados
- AND cada alumno incluye su estado general, actividades aprobadas, total y % de avance

#### Escenario: filtro por materia

- GIVEN alumnos en materias X e Y
- WHEN GET /api/analisis/monitor-general?materia_id=X
- THEN solo se devuelven alumnos con datos en materia X

#### Escenario: filtro por comisión

- GIVEN alumnos con entrada_padron.comision="A" y "B"
- WHEN GET /api/analisis/monitor-general?comision=A
- THEN solo se devuelven alumnos de comisión A

#### Escenario: filtro por regional

- GIVEN alumnos con entrada_padron.regional="Norte" y "Sur"
- WHEN GET /api/analisis/monitor-general?regional=Norte
- THEN solo se devuelven alumnos de regional Norte

#### Escenario: búsqueda textual por nombre

- WHEN GET /api/analisis/monitor-general?q=Martín
- THEN solo se devuelven alumnos cuyo nombre o apellido contenga "Martín" (case-insensitive)

#### Escenario: estado "sin_datos" para alumno sin calificaciones

- GIVEN un alumno en el padrón sin calificaciones asociadas
- WHEN GET /api/analisis/monitor-general
- THEN el alumno aparece con `estado: "sin_datos"`, `aprobadas: 0`, `total: 0`

#### Escenario: ADMIN tiene acceso al monitor general

- WHEN un ADMIN solicita GET /api/analisis/monitor-general
- THEN responde 200 (misma vista que COORDINADOR, scope global)

#### Escenario: PROFESOR no tiene acceso al monitor general

- WHEN un PROFESOR solicita GET /api/analisis/monitor-general
- THEN responde 403 Forbidden

### R-ANA-07 — Monitor de seguimiento (TUTOR/PROFESOR) (F2.8)

`GET /api/analisis/monitor-seguimiento?materia_id=&alumno_id=`

El sistema DEBE devolver el estado detallado de actividades de los alumnos asignados al TUTOR o PROFESOR autenticado, filtrable por materia y por alumno. El scope DEBE limitarse a los alumnos de las asignaciones del usuario. Cada registro incluye: alumno (nombre, apellido), actividad, nota (numérica o textual), resultado (aprobado/desaprobado), y estado general del alumno (al día / atrasado / sin datos).

#### Escenario: TUTOR consulta seguimiento de su materia

- WHEN un TUTOR solicita GET /api/analisis/monitor-seguimiento?materia_id=X
- THEN responde 200 con el detalle de actividades de los alumnos de sus asignaciones en materia X

#### Escenario: filtro por alumno específico

- WHEN un PROFESOR solicita GET /api/analisis/monitor-seguimiento?materia_id=X&alumno_id=UUID
- THEN responde 200 con el detalle solo del alumno especificado (si pertenece a su asignación)

#### Escenario: PROFESOR no ve alumnos de otra asignación

- GIVEN un PROFESOR con asignación A, alumnos de asignación B en misma materia
- WHEN GET /api/analisis/monitor-seguimiento?materia_id=X
- THEN los alumnos de asignación B NO aparecen en la respuesta

#### Escenario: TUTOR con múltiples asignaciones ve todas

- GIVEN un TUTOR con asignaciones en materias X e Y
- WHEN GET /api/analisis/monitor-seguimiento
- THEN responde 200 con alumnos de AMBAS asignaciones

#### Escenario: respuesta incluye estado general por alumno

- WHEN GET /api/analisis/monitor-seguimiento?materia_id=X
- THEN cada grupo de actividades por alumno incluye un campo `estado_general` (al_dia | atrasado | sin_datos)

### R-ANA-08 — Monitor de seguimiento (COORDINADOR/ADMIN) (F2.9)

`GET /api/analisis/monitor-seguimiento?materia_id=&alumno_id=&desde=&hasta=`

El sistema DEBE extender la funcionalidad de R-ANA-07 para COORDINADOR y ADMIN, agregando: (a) scope global (todas las asignaciones de la materia), (b) filtro opcional de rango de fechas (`desde` y `hasta` como query params ISO 8601) para acotar el período de análisis. El filtro de fechas DEBE aplicarse sobre el campo `periodo` de `Calificacion` o sobre `created_at` cuando `periodo` no esté disponible.

#### Escenario: COORDINADOR ve seguimiento global

- WHEN un COORDINADOR solicita GET /api/analisis/monitor-seguimiento?materia_id=X
- THEN responde 200 con actividades de alumnos de TODAS las asignaciones de materia X

#### Escenario: filtro por rango de fechas

- WHEN GET /api/analisis/monitor-seguimiento?materia_id=X&desde=2026-01-01&hasta=2026-06-30
- THEN responde 200 con actividades dentro del período especificado

#### Escenario: ADMIN ve seguimiento global con todos los filtros

- WHEN un ADMIN solicita GET /api/analisis/monitor-seguimiento?materia_id=X&alumno_id=UUID&desde=2026-01-01&hasta=2026-06-30
- THEN responde 200 con datos filtrados por materia, alumno y rango de fechas, scope global

#### Escenario: PROFESOR no puede usar filtro de fechas

- WHEN un PROFESOR solicita GET /api/analisis/monitor-seguimiento?materia_id=X&desde=2026-01-01
- THEN el parámetro `desde` y `hasta` son ignorados (sin error) y se responde con scope propio sin filtro temporal

#### Escenario: rango inválido (desde > hasta)

- WHEN GET /api/analisis/monitor-seguimiento?desde=2026-06-30&hasta=2026-01-01
- THEN responde 422 con mensaje de error "desde debe ser anterior o igual a hasta"
