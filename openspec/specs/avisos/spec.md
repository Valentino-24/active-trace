# Especificación: Avisos

## Creación y Gestión (F3.5)

### AT-01: Crear aviso con alcance global
- Dado un COORDINADOR autenticado con permiso `avisos:publicar`
- Cuando envía `POST /api/avisos` con titulo, cuerpo, alcance="Global", inicio_en, fin_en, orden=1
- Entonces el sistema responde 201
- Y se crea un registro en `aviso` con activo=true

### AT-02: Crear aviso con alcance PorMateria
- Dado un COORDINADOR autenticado
- Cuando envía `POST /api/avisos` con alcance="PorMateria", materia_id=uuid, rol_destino="PROFESOR"
- Entonces el sistema responde 201
- Y el aviso queda asociado a esa materia

### AT-03: Rechazar creación sin campos requeridos
- Dado un COORDINADOR autenticado
- Cuando envía `POST /api/avisos` sin titulo
- Entonces responde 422

### AT-04: Modificar aviso (PATCH)
- Dado que existe un aviso
- Cuando se envía `PATCH /api/avisos/{id}` con `{"titulo": "Nuevo título"}`
- Entonces responde 200
- Y el aviso se actualiza

### AT-05: Desactivar aviso (PATCH activo=false)
- Dado un aviso activo
- Cuando se envía `PATCH /api/avisos/{id}` con `{"activo": false}`
- Entonces responde 200
- Y el aviso ya no aparece en `mis-avisos`

### AT-06: Eliminar aviso (soft delete)
- Dado un COORDINADOR autenticado
- Cuando envía `DELETE /api/avisos/{id}`
- Entonces responde 200
- Y el aviso queda con deleted_at seteado

### AT-07: Listar avisos con contadores
- Dado un COORDINADOR autenticado
- Cuando consulta `GET /api/avisos`
- Entonces recibe una lista con total_vistos y total_acks por aviso
- Y los totales reflejan los acknowledgments existentes

## Visualización por destinatario (RN-18, RN-20)

### AT-08: Usuario ve avisos globales
- Dado un PROFESOR autenticado, sin asignación específica
- Cuando consulta `GET /api/avisos/mis-avisos`
- Entonces recibe avisos con alcance Global que están dentro de su ventana de vigencia

### AT-09: Usuario ve avisos PorMateria solo si está asignado
- Dado un PROFESOR con asignación a materia A pero no a materia B
- Y existe un aviso PorMateria para materia B
- Cuando consulta `GET /api/avisos/mis-avisos`
- Entonces NO recibe el aviso de materia B

### AT-10: Usuario ve avisos PorRol solo si coincide su rol
- Dado un TUTOR autenticado
- Y existe un aviso PorRol con rol_destino="PROFESOR"
- Cuando consulta `GET /api/avisos/mis-avisos`
- Entonces NO recibe ese aviso

### AT-11: Fuera de ventana de vigencia no se muestra (RN-18)
- Dado un aviso con inicio_en en el futuro
- Cuando cualquier usuario consulta `GET /api/avisos/mis-avisos`
- Entonces NO recibe ese aviso

### AT-12: Avisos ordenados por orden ASC
- Dado un usuario con múltiples avisos visibles
- Cuando consulta `GET /api/avisos/mis-avisos`
- Entonces los avisos vienen ordenados por `orden` ASC (menor = mayor prioridad)

## Acknowledgment (RN-19)

### AT-13: Acusar recibo de aviso
- Dado un DOCENTE autenticado
- Y un aviso visible con requiere_ack=true
- Cuando envía `POST /api/avisos/{id}/ack`
- Entonces responde 201
- Y se crea un registro en `acknowledgment_aviso`

### AT-14: Aviso acusado ya no aparece
- Dado un DOCENTE que acusó un aviso con requiere_ack=true
- Cuando consulta `GET /api/avisos/mis-avisos`
- Entonces ese aviso ya no aparece en la lista

### AT-15: Aviso sin requiere_ack sigue apareciendo
- Dado un DOCENTE que ve un aviso con requiere_ack=false
- El aviso se muestra siempre (no requiere ack para ocultarse)

### AT-16: Rechazar ack duplicado
- Dado un DOCENTE que ya acusó un aviso
- Cuando intenta acusar nuevamente
- Entonces responde 409 "Ya has confirmado este aviso"

### AT-17: Rechazar ack en aviso que no requiere
- Dado un aviso con requiere_ack=false
- Cuando un usuario intenta acusar
- Entonces responde 409 "Este aviso no requiere confirmación"

### AT-18: Listar acuses de un aviso (gestión)
- Dado un COORDINADOR autenticado con permiso `avisos:publicar`
- Y un aviso con acknowledgments
- Cuando consulta `GET /api/avisos/{id}/acks`
- Entonces recibe la lista de usuarios que acusaron con sus fechas

## Permisos

### AT-19: 403 sin permiso avisos:publicar en endpoints de gestión
- Dado un usuario SIN permiso `avisos:publicar`
- Cuando intenta POST/PATCH/DELETE /api/avisos/*
- Entonces recibe 403

### AT-20: 200 en mis-avisos y ack sin permiso especial
- Dado cualquier usuario autenticado (incluso sin permisos especiales)
- Cuando consulta GET /api/avisos/mis-avisos o POST /api/avisos/{id}/ack
- Entonces recibe 200 (no requiere permiso)

### AT-21: 401 sin token
- Dado un request SIN token JWT
- Cuando intenta cualquier endpoint de /api/avisos/*
- Entonces recibe 401
