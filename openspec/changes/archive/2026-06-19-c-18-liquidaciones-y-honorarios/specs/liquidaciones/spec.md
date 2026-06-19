# Especificacion: Liquidaciones

## Calculo

### AT-01: Calcular liquidacion del periodo
- Dado cohorte con docentes activos con asignaciones y salarios configurados
- Cuando POST /api/liquidaciones/calcular
- Entonces genera liquidaciones con monto_base + monto_plus = total

### AT-02: Plus no acumulativo por grupo
- Dado docente con 3 materias del grupo PROG
- Cuando se calcula liquidacion
- Entonces monto_plus = 1 × Plus(PROG, PROFESOR), no 3×

### AT-03: Plus de múltiples grupos se suman
- Dado docente con materias de PROG y BD
- Cuando se calcula
- Entonces monto_plus = Plus(PROG) + Plus(BD)

### AT-04: Materia sin grupo_plus no genera plus
- Dado docente con materia sin grupo_plus asignado
- Cuando se calcula
- Entonces monto_plus no incluye plus por esa materia

## Cierre

### AT-05: Cerrar liquidacion
- Dado liquidacion Abierta
- Cuando PATCH /api/liquidaciones/{id}/cerrar
- Entonces 200 y estado = Cerrada

### AT-06: Liquidacion cerrada es inmutable
- Dado liquidacion Cerrada
- Cuando se intenta cerrar nuevamente
- Entonces 409 "Ya cerrada"

## Segmentacion

### AT-07: Docente facturador excluido
- Dado docente con facturador=True
- Cuando se calcula liquidacion
- Entonces excluido_por_factura = True y no suma al total general

### AT-08: NEXO se calcula por separado
- Dado docente con rol=NEXO
- Entonces es_nexo = True

## Permisos

### AT-09: 403 sin permiso
- Dado usuario sin `liquidaciones:gestionar`
- Cuando intenta POST /api/liquidaciones/calcular
- Entonces 403
