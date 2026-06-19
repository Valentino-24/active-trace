# Especificación: Guardias

## Guardia

### AT-01: TUTOR registra una guardia
- Dado un TUTOR autenticado con permiso `guardias:gestionar`
- Cuando envía `POST /api/guardias` con datos válidos (asignacion_id, materia_id, carrera_id, cohorte_id, dia, horario)
- Entonces el sistema responde 201
- Y se crea un registro en `guardia` con estado="Pendiente"

### AT-02: PROFESOR registra una guardia
- Dado un PROFESOR autenticado con permiso `guardias:gestionar`
- Cuando envía `POST /api/guardias` con datos válidos
- Entonces el sistema responde 201

### AT-03: Listar guardias con filtros
- Dado un TUTOR que ha registrado varias guardias
- Cuando consulta `GET /api/guardias?materia_id=X&estado=Pendiente`
- Entonces recibe solo las guardias que coinciden con los filtros
- Y el campo `total` refleja la cantidad correcta

### AT-04: PROFESOR/TUTOR ve solo sus propias guardias
- Dado un TUTOR con guardias registradas
- Cuando consulta `GET /api/guardias`
- Entonces solo recibe las guardias donde `asignacion_id` le pertenece

### AT-05: COORDINADOR ve todas las guardias del tenant
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/guardias`
- Entonces recibe guardias de todas las asignaciones del tenant

### AT-06: Editar estado y comentarios de guardia
- Dado un TUTOR que registró una guardia en estado "Pendiente"
- Cuando envía `PATCH /api/guardias/{id}` con `{"estado": "Realizada", "comentarios": "Se resolvieron dudas"}`
- Entonces el sistema responde 200
- Y la guardia queda con estado="Realizada" y comentarios actualizados

### AT-07: Exportar guardias a CSV
- Dado un usuario autenticado con permiso `guardias:gestionar`
- Cuando consulta `GET /api/guardias/export?materia_id=X`
- Entonces recibe una respuesta con `Content-Type: text/csv`
- Y el contenido CSV incluye una fila de encabezados y los datos filtrados

### AT-08: 403 sin permiso guardias:gestionar
- Dado un usuario SIN permiso `guardias:gestionar`
- Cuando intenta cualquier endpoint de `/api/guardias/*`
- Entonces recibe 403 Forbidden

### AT-09: 401 sin token
- Dado un request SIN token JWT
- Cuando intenta cualquier endpoint de `/api/guardias/*`
- Entonces recibe 401 Unauthorized

### AT-10: Validación de campos requeridos en creación
- Dado un TUTOR autenticado
- Cuando envía `POST /api/guardias` sin `materia_id`
- Entonces el sistema responde 422 con error de validación
