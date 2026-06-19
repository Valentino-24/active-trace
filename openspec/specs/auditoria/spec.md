# Especificacion: Panel de Auditoria

## Acciones por Dia (F9.1)

### AT-01: Agregacion diaria
- Dado ADMIN con `auditoria:ver`
- Cuando GET /api/auditoria/acciones-por-dia?desde=2025-01-01&hasta=2025-06-30
- Entonces devuelve array de {fecha, total} ordenado ASC

### AT-02: COORDINADOR ve solo sus acciones
- Dado COORDINADOR
- Cuando consulta acciones-por-dia
- Entonces solo recibe conteos de sus propias acciones

## Por Docente (F9.1)

### AT-03: Agregacion por docente y tipo de accion
- Dado ADMIN
- Cuando GET /api/auditoria/por-docente
- Entonces devuelve array de {actor_id, accion, total, ultima_fecha}

### AT-04: COORDINADOR ve solo sus datos
- Dado COORDINADOR
- Cuando por-docente
- Entonces solo sus propias metricas

## Recientes (F9.1)

### AT-05: Ultimas acciones con limite configurable
- Dado ADMIN
- Cuando GET /api/auditoria/recientes?limit=50
- Entonces 50 registros mas recientes

### AT-06: Limite por defecto 200
- Cuando GET /api/auditoria/recientes sin limit
- Entonces max 200

## Log Completo (F9.2)

### AT-07: Filtros combinados
- Dado ADMIN
- Cuando GET /api/auditoria/log?fecha_desde=X&fecha_hasta=Y&materia_id=Z&accion=CALIFICACIONES_IMPORTAR
- Entonces solo registros que cumplen todos los filtros

### AT-08: Sin filtros devuelve todos
- Cuando GET /api/auditoria/log sin params
- Entonces todos los registros del tenant

## Permisos

### AT-09: 403 sin auditoria:ver
### AT-10: 401 sin token
