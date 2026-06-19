# Calificaciones

> Importación de calificaciones desde archivos LMS con detección de columnas, preview, selección de actividades, confirmación y derivación de `aprobado` contra el umbral configurado. Incluye importación de reporte de finalización para detectar entregas sin corregir (F1.2).

## Permisos

| Permiso | Descripción | Asignado a |
|---------|-------------|-----------|
| `calificaciones:importar` | Preview, import y finalización | PROFESOR (scope propia asignación), COORDINADOR, ADMIN |
| `calificaciones:ver` | Consultar calificaciones | PROFESOR (scope propia asignación), COORDINADOR, ADMIN |

## Requisitos

### R-CAL-01 — Vista previa de import desde archivo

`POST /api/calificaciones/preview`

El sistema DEBE aceptar un archivo `.xlsx` o `.csv` y devolver las columnas detectadas clasificadas por tipo (numérica si el encabezado termina en `(Real)` — RN-01; textual en caso contrario — RN-02), las filas parseadas y una lista de errores por fila.

#### Escenario: preview exitoso con columnas mixtas

- GIVEN un archivo LMS con columnas `TP1 (Real)` y `TP2 (Cualitativo)`
- WHEN se envía POST /preview con `materia_id`, `cohorte_id` y el archivo
- THEN responde 200 con `columnas_detectadas` clasificadas por tipo, `filas` con datos parseados y `total_filas`
- AND la columna `TP1 (Real)` se marca como `tipo: "numerica"` y `TP2 (Cualitativo)` como `tipo: "textual"`

#### Escenario: preview con errores de parseo por fila

- GIVEN un archivo con 10 filas, 2 con datos inválidos
- WHEN se envía POST /preview
- THEN responde 200 con `errores` listando cada fila inválida y su mensaje
- AND las filas válidas se incluyen en la preview

#### Escenario: archivo no soportado

- GIVEN un archivo `.pdf`
- WHEN se envía POST /preview
- THEN responde 400 con mensaje "Formato no soportado. Use .xlsx o .csv"

### R-CAL-02 — Confirmar import de calificaciones

`POST /api/calificaciones/import`

El sistema DEBE crear registros `Calificacion` a partir de las filas confirmadas, matcheando alumnos contra `EntradaPadron` por `email_hash`, derivando `aprobado` contra el `UmbralMateria` vigente, y registrando audit `CALIFICACIONES_IMPORTAR`.

#### Escenario: import exitoso con aprobados derivados

- GIVEN un umbral configurado con `umbral_pct=0.60` y `max_nota=100`
- WHEN se importan calificaciones con notas `85.0` (numérica) y `"Satisfactorio"` (textual)
- THEN se crean registros `Calificacion` con `aprobado=true` para ambos casos
- AND se registra audit `CALIFICACIONES_IMPORTAR` con detalle de total_notas y materia

#### Escenario: alumno no encontrado en padrón

- GIVEN una fila con email que no existe en `EntradaPadron` del tenant
- WHEN se envía POST /import
- THEN responde 400 con error listando los emails no reconocidos
- AND no se persiste ninguna calificación (transacción abortada)

#### Escenario: nota numérica no alcanza umbral

- GIVEN `umbral_pct=0.60` y `max_nota=100` (mínimo 60)
- WHEN se importa una nota numérica `45.0`
- THEN `aprobado=false`

#### Escenario: nota textual no está en valores aprobatorios

- GIVEN `valores_aprobatorios=["Satisfactorio", "Supera lo esperado"]`
- WHEN se importa `nota_textual="No satisfactorio"`
- THEN `aprobado=false`

#### Escenario: sin nota numérica ni textual

- GIVEN una fila sin nota ni nota_textual
- WHEN se procesa la calificación
- THEN `aprobado=false` y `origen="Importado"`

### R-CAL-03 — Importar reporte de finalización (F1.2)

`POST /api/calificaciones/importar-finalizacion`

El sistema DEBE cruzar el reporte de finalización del LMS con las calificaciones importadas para identificar actividades textuales entregadas pero sin calificación (RN-07, RN-08).

#### Escenario: detecta TPs textuales entregados sin nota

- GIVEN un reporte que indica TP1 (textual) entregado por alumno "Juan"
- AND "Juan" no tiene calificación registrada para TP1
- WHEN se envía POST /importar-finalizacion
- THEN responde 200 listando `{alumno: "Juan", actividad: "TP1", estado: "Sin_corregir"}`

#### Escenario: excluye actividades numéricas del reporte

- GIVEN un reporte con TP numérico entregado sin nota
- WHEN se envía POST /importar-finalizacion
- THEN la actividad numérica no aparece en el listado (RN-08)

### R-CAL-04 — Listar calificaciones

`GET /api/calificaciones?materia_id=&cohorte_id=`

El sistema DEBE devolver las calificaciones del tenant filtradas por materia y cohorte, con paginación y scope de tenant.

#### Escenario: listado filtrado con paginación

- GIVEN 50 calificaciones para materia X, cohorte Y
- WHEN GET /api/calificaciones?materia_id=X&cohorte_id=Y&skip=0&limit=20
- THEN responde 200 con `items` (20 registros) y `total` (50)

#### Escenario: PROFESOR solo ve su propia asignación

- GIVEN un PROFESOR con asignación A en materia X
- AND existen calificaciones de asignación B en la misma materia X
- WHEN el PROFESOR lista calificaciones de materia X
- THEN solo se devuelven las de asignación A
