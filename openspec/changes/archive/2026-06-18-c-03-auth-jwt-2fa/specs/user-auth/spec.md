## ADDED Requirements

### Requirement: Login con email y password

El sistema SHALL autenticar usuarios mediante email y contraseña, utilizando Argon2id para verificar el hash. En caso de credenciales válidas, SHALL emitir un par de tokens (access + refresh). Si el usuario tiene 2FA habilitado, SHALL emitir un session_token temporal en lugar del par completo, requiriendo un paso adicional de verificación TOTP.

#### Scenario: Login exitoso sin 2FA

- **WHEN** un usuario envía `POST /api/auth/login` con email y contraseña válidos, y no tiene 2FA habilitado
- **THEN** el sistema responde `200 OK` con un access token (JWT, 15 min de expiración) y un refresh token (opaco, 7 días de expiración)

#### Scenario: Login con credenciales inválidas

- **WHEN** un usuario envía `POST /api/auth/login` con email o contraseña incorrectos
- **THEN** el sistema responde `401 Unauthorized` con un mensaje de error genérico (sin revelar si el email existe o no)

#### Scenario: Login con usuario inactivo

- **WHEN** un usuario inactivo (is_active=False) intenta iniciar sesión con credenciales válidas
- **THEN** el sistema responde `403 Forbidden`

#### Scenario: Login con 2FA habilitado

- **WHEN** un usuario con 2FA habilitado envía credenciales válidas
- **THEN** el sistema responde `200 OK` con `requires_2fa: true` y un `session_token` temporal (JWT, 5 min de expiración)
- **AND** el sistema NO emite access token ni refresh token en este paso

### Requirement: Rate limiting en login

El sistema SHALL limitar los intentos de login a 5 por minuto por combinación única de IP origen + email destino. Superado el límite, SHALL rechazar con `429 Too Many Requests`.

#### Scenario: Rate limit no alcanzado

- **WHEN** un usuario envía 4 intentos de login en menos de 60 segundos
- **THEN** el sistema procesa cada intento normalmente

#### Scenario: Rate limit excedido

- **WHEN** un usuario envía 6 intentos de login en menos de 60 segundos
- **THEN** el sistema responde con `429 Too Many Requests` en el sexto intento

### Requirement: Refresh token con rotación

El sistema SHALL permitir renovar un access token expirado mediante un refresh token válido. Al usar un refresh token, el sistema SHALL invalidar ese token (marcar como revoked) y emitir un nuevo par (access + refresh). Si un refresh token ya revocado es reutilizado, el sistema SHALL invalidar TODOS los refresh tokens del usuario (detección de robo de sesión).

#### Scenario: Refresh exitoso

- **WHEN** un usuario envía `POST /api/auth/refresh` con un refresh token válido y no revocado
- **THEN** el sistema responde `200 OK` con un nuevo access token y un nuevo refresh token
- **AND** el refresh token anterior queda marcado como revocado

#### Scenario: Refresh con token revocado (reuso detectado)

- **WHEN** un usuario envía `POST /api/auth/refresh` con un refresh token que ya fue revocado
- **THEN** el sistema responde `401 Unauthorized`
- **AND** el sistema invalida (revoca) TODOS los refresh tokens activos de ese usuario

#### Scenario: Refresh con token expirado

- **WHEN** un usuario envía `POST /api/auth/refresh` con un refresh token expirado
- **THEN** el sistema responde `401 Unauthorized`

### Requirement: Logout

El sistema SHALL permitir cerrar la sesión activa, revocando el refresh token asociado.

#### Scenario: Logout exitoso

- **WHEN** un usuario autenticado envía `POST /api/auth/logout` con su refresh token actual
- **THEN** el sistema revoca ese refresh token
- **AND** responde `204 No Content`

#### Scenario: Logout con token inválido

- **WHEN** un usuario envía `POST /api/auth/logout` con un refresh token inválido o expirado
- **THEN** el sistema responde `204 No Content` (idempotente — no revela validez del token)
