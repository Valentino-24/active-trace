## ADDED Requirements

### Requirement: Solicitud de recuperación de contraseña

El sistema SHALL permitir a un usuario no autenticado solicitar la recuperación de su contraseña mediante su email. El sistema SHALL generar un token de un solo uso con expiración de 30 minutos y almacenarlo. Para el MVP, el sistema SHALL registrar el token en el log y devolverlo en la respuesta (en producción se enviará por email).

#### Scenario: Solicitar recuperación para email existente

- **WHEN** un usuario no autenticado envía `POST /api/auth/forgot` con un email registrado en el sistema
- **THEN** el sistema genera un token de recuperación único asociado a ese usuario
- **AND** el token tiene expiración de 30 minutos
- **AND** el sistema responde `200 OK` incluyendo el token en la respuesta (MVP)
- **AND** el sistema invalida cualquier token de recuperación anterior para el mismo usuario

#### Scenario: Solicitar recuperación para email inexistente

- **WHEN** un usuario no autenticado envía `POST /api/auth/forgot` con un email no registrado
- **THEN** el sistema responde `200 OK` (respuesta genérica para no revelar qué emails existen)
- **AND** el sistema NO genera ningún token

### Requirement: Reseteo de contraseña

El sistema SHALL permitir cambiar la contraseña utilizando un token de recuperación válido. Una vez usado, el token SHALL quedar invalidado.

#### Scenario: Resetear contraseña con token válido

- **WHEN** un usuario envía `POST /api/auth/reset` con un token de recuperación válido y una nueva contraseña
- **THEN** el sistema actualiza el password hash del usuario
- **AND** marca el token como usado
- **AND** revoca TODOS los refresh tokens activos del usuario (cierra todas las sesiones)
- **AND** responde `204 No Content`

#### Scenario: Resetear contraseña con token expirado

- **WHEN** un usuario envía `POST /api/auth/reset` con un token de recuperación expirado
- **THEN** el sistema responde `401 Unauthorized`

#### Scenario: Resetear contraseña con token ya usado

- **WHEN** un usuario envía `POST /api/auth/reset` con un token de recuperación ya marcado como usado
- **THEN** el sistema responde `401 Unauthorized`

#### Scenario: Nueva contraseña inválida

- **WHEN** un usuario envía `POST /api/auth/reset` con un token válido pero una nueva contraseña que no cumple los requisitos de fortaleza
- **THEN** el sistema responde `422 Unprocessable Entity` con el detalle de validación
