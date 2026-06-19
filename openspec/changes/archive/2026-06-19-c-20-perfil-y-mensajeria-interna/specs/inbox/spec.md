# Especificacion: Inbox (Mensajeria Interna)

### AT-01: Enviar mensaje
- Dado usuario A autenticado
- Cuando POST /api/inbox/enviar con destinatario_id=B, asunto="Hola", texto="..."
- Entonces 201

### AT-02: Listar recibidos
- GET /api/inbox/recibidos → mensajes donde destinatario=current_user

### AT-03: Listar enviados
- GET /api/inbox/enviados → mensajes donde remitente=current_user

### AT-04: Marcar como leido
- PATCH /api/inbox/{id}/leido → leido=true, leido_at=now

### AT-05: 401 sin token
### AT-06: No ve mensajes de otros usuarios
