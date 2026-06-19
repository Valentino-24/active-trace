# Especificación: Encuentros

## SlotEncuentro

### AT-01: Crear slot recurrente genera N instancias
- Dado un PROFESOR autenticado con permiso `encuentros:gestionar`
- Cuando envía `POST /api/encuentros/slots` con `cant_semanas=15`, `fecha_inicio="2026-03-10"`, `dia_semana="Lunes"`, `hora="18:00"`
- Entonces el sistema responde 201 con `total_instancias=15`
- Y existen 15 registros en `instancia_encuentro` vinculados al slot
- Y cada instancia tiene fecha = fecha_inicio + N*7 días, hora="18:00", estado="Programado"

### AT-02: Crear slot fecha única genera 1 instancia
- Dado un PROFESOR autenticado con permiso `encuentros:gestionar`
- Cuando envía `POST /api/encuentros/slots` con `cant_semanas=0`, `fecha_inicio="2026-03-10"`, `fecha_unica="2026-03-10"`
- Entonces el sistema responde 201 con `total_instancias=1`
- Y existe 1 instancia con fecha = fecha_unica

### AT-03: Rechazar slot con modo ambiguo (ambos o ninguno)
- Dado un PROFESOR autenticado
- Cuando envía `POST /api/encuentros/slots` con `cant_semanas=0` y `fecha_unica=null`
- Entonces el sistema responde 422 con error de validación
- Y no se crea ningún slot ni instancia

### AT-04: Rechazar slot con `cant_semanas` y `fecha_unica` simultáneamente
- Dado un PROFESOR autenticado
- Cuando envía `POST /api/encuentros/slots` con `cant_semanas=5` y `fecha_unica="2026-03-10"`
- Entonces el sistema responde 422 con error de validación

### AT-05: Editar instancia de encuentro (estado, URLs, comentario)
- Dado que existe una instancia con estado="Programado"
- Cuando un PROFESOR con permiso envía `PATCH /api/encuentros/instancias/{id}` con `{"estado": "Realizado", "video_url": "https://youtube.com/xxx"}`
- Entonces el sistema responde 200
- Y la instancia queda con estado="Realizado" y video_url="https://youtube.com/xxx"

### AT-06: Editar instancia no afecta al slot ni a otras instancias
- Dado un slot con 3 instancias (ids: A, B, C) en estado "Programado"
- Cuando se edita instancia A a estado "Realizado"
- Entonces las instancias B y C permanecen en "Programado"
- Y el slot no se modifica (RN-14)

### AT-07: Listar instancias por materia y rango de fechas
- Dado un PROFESOR con asignación a materia X
- Cuando envía `GET /api/encuentros/instancias?materia_id=X&desde=2026-03-01&hasta=2026-04-01`
- Entonces recibe solo las instancias de materia X en ese rango
- Y el total refleja la cantidad correcta

### AT-08: PROFESOR ve solo instancias de sus materias
- Dado un PROFESOR con asignación a materia A pero no a materia B
- Cuando consulta `GET /api/encuentros/instancias`
- Entonces no recibe instancias de materia B

### AT-09: COORDINADOR ve instancias de todas las materias
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/encuentros/instancias`
- Entonces recibe instancias de todas las materias del tenant

### AT-10: Generar bloque HTML
- Dado que existen instancias de una materia con estado "Realizado" y video_url
- Cuando se consulta `GET /api/encuentros/instancias/{id}/html`
- Entonces el sistema responde 200 con un campo `html` que contiene markup HTML
- Y el HTML incluye los títulos, fechas, enlaces a meet y video de las instancias

### AT-11: Vista admin transversal (F6.5)
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/encuentros/admin`
- Entonces recibe instancias de todas las materias del tenant
- Y los filtros por materia, fecha, estado funcionan

### AT-12: 403 sin permiso encuentros:gestionar
- Dado un usuario SIN permiso `encuentros:gestionar`
- Cuando intenta cualquier endpoint de `/api/encuentros/*`
- Entonces recibe 403 Forbidden

### AT-13: 401 sin token
- Dado un request SIN token JWT
- Cuando intenta cualquier endpoint de `/api/encuentros/*`
- Entonces recibe 401 Unauthorized
