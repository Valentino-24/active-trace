# Especificacion: Salarios (Base + Plus)

## SalarioBase

### AT-01: Crear salario base
- Dado FINANZAS con `liquidaciones:configurar-salarios`
- Cuando POST /api/salarios/base con rol, monto, desde
- Entonces 201

### AT-02: Vigencia — buscar vigente en fecha
- Dado SalarioBase PROFESOR=50000 desde 2025-01-01
- Cuando se consulta el vigente para fecha 2025-06-15
- Entonces devuelve 50000

### AT-03: Actualizar monto
- Dado un SalarioBase existente
- Cuando PATCH con nuevo monto
- Entonces 200 y se actualiza

### AT-04: Eliminar (soft delete)
- Dado SalarioBase existente
- Cuando DELETE
- Entonces 200

## SalarioPlus

### AT-05: Crear plus
- Dado FINANZAS con `liquidaciones:configurar-salarios`
- Cuando POST /api/salarios/plus con grupo, rol, monto, desde
- Entonces 201

### AT-06: Listar plus vigentes para grupo y rol
- Dado plus PROG/PROFESOR=5000 vigente
- Cuando se consulta por grupo=PROG, rol=PROFESOR, fecha=hoy
- Entonces devuelve el plus

### AT-07: CRUD completo de plus
- PATCH y DELETE sobre SalarioPlus funcionan correctamente

## Permisos

### AT-08: 403 sin permiso configurar-salarios
- Dado usuario sin `liquidaciones:configurar-salarios`
- Cuando intenta POST /api/salarios/base
- Entonces 403
