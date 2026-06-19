# Especificación: Tareas Internas

## Creación y Asignación (F8.2)

### AT-01: Crear tarea asignada a un docente
- Dado un PROFESOR autenticado con permiso `tareas:gestionar`
- Cuando envía `POST /api/tareas` con asignado_a, materia_id, descripcion
- Entonces responde 201
- Y la tarea queda con estado="Pendiente" y asignado_por=current_user

### AT-02: Rechazar creación sin campos requeridos
- Dado un PROFESOR autenticado
- Cuando envía `POST /api/tareas` sin descripcion
- Entonces responde 422

## Vista de Mis Tareas (F8.1)

### AT-03: Usuario ve solo sus tareas asignadas
- Dado un PROFESOR con tareas donde asignado_a es él y otras donde es otro usuario
- Cuando consulta `GET /api/tareas/mias`
- Entonces solo recibe las tareas donde asignado_a = current_user

### AT-04: Filtrar mis tareas por estado
- Dado un PROFESOR con tareas en distintos estados
- Cuando consulta `GET /api/tareas/mias?estado=Pendiente`
- Entonces solo recibe tareas en estado Pendiente

### AT-05: Filtrar mis tareas por materia
- Dado un PROFESOR con tareas de diferentes materias
- Cuando consulta `GET /api/tareas/mias?materia_id=X`
- Entonces solo recibe tareas de materia X

### AT-06: Mis tareas incluyen último comentario
- Dado una tarea con 2 comentarios
- Cuando se lista en `GET /api/tareas/mias`
- Entonces el campo `ultimo_comentario` contiene el texto del comentario más reciente

## Transiciones de Estado

### AT-07: Transición válida Pendiente → EnProgreso
- Dado una tarea en estado Pendiente
- Cuando se envía `PATCH /api/tareas/{id}/estado` con `{"estado": "EnProgreso"}`
- Entonces responde 200 y la tarea queda en EnProgreso

### AT-08: Transición válida EnProgreso → Resuelta
- Dado una tarea en EnProgreso
- Cuando se cambia a Resuelta
- Entonces responde 200

### AT-09: Transición válida Pendiente → Cancelada
- Dado una tarea en Pendiente
- Cuando se cambia a Cancelada
- Entonces responde 200

### AT-10: Rechazar transición inválida Resuelta → Pendiente (409)
- Dado una tarea en estado Resuelta (terminal)
- Cuando se intenta cambiar a Pendiente
- Entonces responde 409 "Transición inválida"

### AT-11: Rechazar transición inválida Cancelada → EnProgreso (409)
- Dado una tarea en estado Cancelada (terminal)
- Cuando se intenta cambiar a EnProgreso
- Entonces responde 409

## Reasignación (Delegación F8.2)

### AT-12: Reasignar tarea a otro docente
- Dado una tarea asignada a usuario A
- Cuando se envía `PATCH /api/tareas/{id}/asignar` con `{"asignado_a": "usuario-B"}`
- Entonces responde 200
- Y la tarea queda asignada a usuario B

## Comentarios

### AT-13: Agregar comentario a una tarea
- Dado un PROFESOR con acceso a una tarea
- Cuando envía `POST /api/tareas/{id}/comentarios` con texto
- Entonces responde 201
- Y se crea el comentario asociado a la tarea

### AT-14: Listar comentarios de una tarea
- Dado una tarea con 3 comentarios
- Cuando consulta `GET /api/tareas/{id}/comentarios`
- Entonces recibe 3 items ordenados ASC por creado_at

## Admin Global (F8.3)

### AT-15: COORDINADOR ve todas las tareas del tenant
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/tareas`
- Entonces recibe tareas de todos los usuarios, no solo las propias

### AT-16: Filtros combinados en admin
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/tareas?estado=Pendiente&materia_id=X`
- Entonces solo recibe tareas que cumplen ambos filtros

### AT-17: Búsqueda libre por descripción
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/tareas?q=informe`
- Entonces recibe tareas cuya descripción contiene "informe" (case insensitive)

### AT-18: TUTOR/PROFESOR no accede al admin global
- Dado un TUTOR autenticado
- Cuando consulta `GET /api/tareas` (sin /mias)
- Entonces recibe 403

## Permisos

### AT-19: 403 sin permiso tareas:gestionar
- Dado un usuario SIN permiso `tareas:gestionar`
- Cuando intenta cualquier endpoint de /api/tareas/*
- Entonces recibe 403

### AT-20: 401 sin token
- Dado un request SIN token JWT
- Cuando intenta cualquier endpoint de /api/tareas/*
- Entonces recibe 401
