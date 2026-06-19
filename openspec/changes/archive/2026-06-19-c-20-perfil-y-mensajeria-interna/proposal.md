# Proposal: Perfil y Mensajeria Interna

## Intent

Permitir a usuarios editar su perfil y comunicarse entre docentes via mensajeria interna. Hoy no hay mensajeria entre pares ni edicion de datos fiscales.

## Scope

### In Scope
- PATCH perfil propio: nombre, datos fiscales, regional, CUIL (read-only)
- Modelo `Mensaje` — hilo entre 2 usuarios, remitente/destinatario, texto
- Bandeja inbox: listar hilos recibidos, responder en hilo, marcar leido
- Logout explícito (reusa C-03)

### Out of Scope
- Mensajes a alumnos (eso es C-12 comunicaciones)
- Grupos/canales
- Adjuntos en mensajes

## Capabilities

### New
- `perfil`: Edicion de datos propios
- `inbox`: Mensajeria interna entre usuarios

### Modified
None

## Approach

Modelo `Mensaje` (remitente_id, destinatario_id, texto, leido). Endpoints REST. BAJO governance.

## Dependencies
C-07, C-03

## Success Criteria
- [ ] PATCH perfil respeta CUIL read-only
- [ ] Mensajes: enviar, listar hilos, responder, marcar leido
- [ ] ≥10 tests
