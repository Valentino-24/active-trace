# Especificacion: Perfil

### AT-01: Editar campos permitidos
- Dado usuario autenticado
- Cuando PATCH /api/perfil con display_name="Nuevo Nombre"
- Entonces 200 y nombre actualizado

### AT-02: CUIL es solo lectura
- Dado request con cuil="20-12345678-9"
- Cuando PATCH /api/perfil
- Entonces 422 "CUIL no modificable"

### AT-03: Ver perfil propio
- Dado usuario autenticado
- Cuando GET /api/perfil
- Entonces 200 con datos completos

### AT-04: 401 sin token
- Entonces 401
