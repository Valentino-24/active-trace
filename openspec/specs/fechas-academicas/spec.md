# Especificacion: Fechas Academicas

## CRUD Fechas

### AT-01: Crear fecha academica
- Dado un COORDINADOR autenticado con `estructura:gestionar`
- Cuando envia `POST /api/fechas-academicas` con materia_id, cohorte_id, tipo="Parcial", numero=1, periodo="2025-1", fecha="2025-05-15", titulo="1er Parcial"
- Entonces responde 201

### AT-02: Listar con filtro por materia
- Dado fechas de distintas materias
- Cuando consulta `GET /api/fechas-academicas?materia_id=X`
- Entonces recibe solo las de materia X

### AT-03: Listar con filtro por tipo
- Dado fechas de distintos tipos
- Cuando consulta `GET /api/fechas-academicas?tipo=Parcial`
- Entonces recibe solo Parcial

### AT-04: Listar con filtro por periodo
- Dado fechas en periodos "2025-1" y "2025-2"
- Cuando consulta `GET /api/fechas-academicas?periodo=2025-1`
- Entonces recibe solo las del primer cuatrimestre

### AT-05: Filtros combinados
- Dado fechas de materia X, tipo Parcial, periodo 2025-1
- Cuando consulta con los 3 filtros
- Entonces recibe solo las que cumplen los 3

### AT-06: Actualizar fecha
- Dado una fecha existente
- Cuando envia `PATCH /api/fechas-academicas/{id}` con nueva fecha
- Entonces responde 200 con los datos actualizados

### AT-07: Eliminar fecha (soft delete)
- Dado una fecha existente
- Cuando envia `DELETE /api/fechas-academicas/{id}`
- Entonces responde 200

### AT-08: Validacion de tipo invalido
- Dado un request con tipo="Invalido"
- Cuando envia `POST /api/fechas-academicas`
- Entonces responde 422

## Permisos

### AT-09: 403 sin permiso estructura:gestionar
- Dado un usuario sin `estructura:gestionar`
- Cuando intenta cualquier endpoint de /api/fechas-academicas
- Entonces recibe 403

### AT-10: 401 sin token
- Dado un request sin JWT
- Entonces recibe 401
