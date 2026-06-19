# Especificacion: Facturas

## CRUD Facturas

### AT-01: Crear factura
- Dado FINANZAS con `liquidaciones:gestionar`
- Cuando POST /api/facturas con usuario_id, periodo, detalle
- Entonces 201 con estado=Pendiente

### AT-02: Cambiar estado a Abonada
- Dado factura Pendiente
- Cuando PATCH /api/facturas/{id}/abonar
- Entonces 200 y estado=Abonada, abonada_at != null

### AT-03: Listar facturas con filtros
- Dado facturas de distintos estados
- Cuando GET /api/facturas?estado=Pendiente&usuario_id=X
- Entonces solo las que cumplen filtros

### AT-04: 403 sin permiso
- Dado usuario sin `liquidaciones:gestionar`
- Entonces 403

### AT-05: 401 sin token
- Entonces 401
