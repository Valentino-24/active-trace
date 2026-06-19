# Umbral de Materia

> Configuración del criterio de aprobación por asignación docente (F2.1). Define el porcentaje mínimo de nota (`umbral_pct`) y los valores textuales que cuentan como aprobado (`valores_aprobatorios`). La herencia sigue: umbral específico de asignación → umbral de materia (asignacion_id IS NULL) → defecto 60% (RN-03).

## Permisos

| Permiso | Descripción | Asignado a |
|---------|-------------|-----------|
| `calificaciones:ver` | Consultar umbrales | PROFESOR (scope propia asignación), COORDINADOR, ADMIN |
| `calificaciones:importar` | Modificar umbrales | PROFESOR (scope propia asignación), COORDINADOR, ADMIN |

## Requisitos

### R-UMB-01 — Listar umbrales por materia y cohorte

`GET /api/umbrales?materia_id=&cohorte_id=`

El sistema DEBE devolver los umbrales configurados para la materia y cohorte, incluyendo el umbral global de materia (`asignacion_id IS NULL`) y los específicos por asignación.

#### Escenario: listado con umbrales mixtos

- GIVEN un umbral global con `umbral_pct=0.60` y uno específico con `umbral_pct=0.75`
- WHEN GET /api/umbrales?materia_id=X&cohorte_id=Y
- THEN responde 200 con ambos umbrales, distinguiendo el específico por su `asignacion_id`

#### Escenario: sin umbrales configurados

- GIVEN no existen `UmbralMateria` para la materia X y cohorte Y
- WHEN GET /api/umbrales?materia_id=X&cohorte_id=Y
- THEN responde 200 con `items=[]`

### R-UMB-02 — Actualizar umbral por asignación

`PUT /api/umbrales/{id}`

El sistema DEBE actualizar `umbral_pct` y/o `valores_aprobatorios` del umbral especificado. Si no existe umbral para la asignación, el sistema DEBE crearlo (upsert). PROFESOR solo puede modificar umbrales de su propia asignación (RN-03).

#### Escenario: actualizar umbral_pct

- GIVEN un umbral existente con `umbral_pct=0.60`
- WHEN PUT /api/umbrales/{id} body: `{"umbral_pct": 0.75}`
- THEN responde 200 con el umbral actualizado
- AND las próximas derivaciones de `aprobado` usan 75%

#### Escenario: actualizar valores aprobatorios textuales

- GIVEN `valores_aprobatorios` actual "Satisfactorio", "Supera lo esperado"
- WHEN PUT /api/umbrales/{id} body: `{"valores_aprobatorios": ["Aprobado", "Muy bueno"]}`
- THEN responde 200 con los nuevos valores
- AND los imports posteriores evalúan contra el nuevo conjunto

#### Escenario: PROFESOR modifica umbral de otra asignación

- GIVEN un PROFESOR con asignación A
- WHEN intenta PUT /api/umbrales/{id_del_profesor_B}
- THEN responde 403 Forbidden

### R-UMB-03 — Herencia de umbral en derivación de aprobado

El sistema DEBE aplicar la herencia de umbral al derivar `aprobado`: si existe umbral con `asignacion_id` del docente → usa ese; si no, busca umbral con `asignacion_id IS NULL` para la materia; si no existe ninguno, usa `umbral_pct=0.60` por defecto (RN-03).

#### Escenario: umbral específico tiene prioridad

- GIVEN umbral específico para asignación A con `umbral_pct=0.75` y umbral global de materia con `0.60`
- WHEN se importan calificaciones para la asignación A
- THEN la derivación de `aprobado` usa `0.75`

#### Escenario: umbral global de materia como fallback

- GIVEN no existe umbral para asignación A, pero existe umbral global de materia con `0.70`
- WHEN se importan calificaciones para la asignación A
- THEN la derivación usa `0.70`

#### Escenario: defecto 60% sin umbral configurado

- GIVEN no existe ningún `UmbralMateria` para la materia
- WHEN se importan calificaciones
- THEN la derivación usa `umbral_pct=0.60`
