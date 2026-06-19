# Especificacion: Programas de Materia

## CRUD Programas

### AT-01: Crear programa de materia
- Dado un COORDINADOR autenticado con `estructura:gestionar`
- Cuando envia `POST /api/programas` con materia_id, carrera_id, cohorte_id, titulo, referencia_archivo
- Entonces responde 201 y se crea el programa

### AT-02: Rechazar creacion sin campos requeridos
- Dado un request sin materia_id
- Cuando envia `POST /api/programas`
- Entonces responde 422

### AT-03: Listar programas con filtros
- Dado programas de distintas materias y cohortes
- Cuando consulta `GET /api/programas?materia_id=X&cohorte_id=Y`
- Entonces recibe solo los que coinciden con ambos filtros

### AT-04: Eliminar programa (soft delete)
- Dado un programa existente
- Cuando envia `DELETE /api/programas/{id}`
- Entonces responde 200 y el programa queda con deleted_at

### AT-05: Actualizar referencia de archivo
- Dado un programa existente
- Cuando envia `PATCH /api/programas/{id}` con nueva referencia_archivo
- Entonces responde 200 con los datos actualizados

## Permisos

### AT-06: 403 sin permiso estructura:gestionar
- Dado un usuario sin `estructura:gestionar`
- Cuando intenta cualquier endpoint de /api/programas
- Entonces recibe 403

### AT-07: 401 sin token
- Dado un request sin JWT
- Cuando intenta /api/programas/*
- Entonces recibe 401
