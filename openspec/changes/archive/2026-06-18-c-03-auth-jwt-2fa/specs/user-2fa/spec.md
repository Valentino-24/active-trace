## ADDED Requirements

### Requirement: Enrolamiento de 2FA TOTP

El sistema SHALL permitir a un usuario autenticado generar un secreto TOTP para su cuenta. El sistema SHALL devolver una URI `otpauth://` para que el usuario la asocie a su aplicación autenticadora (Google Authenticator, Authy, etc.).

#### Scenario: Enrolar 2FA exitosamente

- **WHEN** un usuario autenticado envía `POST /api/auth/2fa/enroll`
- **THEN** el sistema genera un nuevo secreto TOTP
- **AND** responde `200 OK` con la URI `otpauth://` y el secreto en base32
- **AND** el sistema NO activa aún el 2FA (requiere verificación)

#### Scenario: Enrolar 2FA cuando ya está activo

- **WHEN** un usuario autenticado con 2FA ya activo envía `POST /api/auth/2fa/enroll`
- **THEN** el sistema responde `409 Conflict`

### Requirement: Verificación de 2FA TOTP

El sistema SHALL permitir verificar un código TOTP contra el secreto almacenado. Si la verificación es correcta, SHALL activar el 2FA para el usuario (enrolamiento) o completar el login (autenticación de dos factores).

#### Scenario: Verificar 2FA en enrolamiento

- **WHEN** un usuario envía `POST /api/auth/2fa/verify` con un `session_token` de enrolamiento y un código TOTP válido
- **THEN** el sistema activa 2FA para el usuario (totp_enabled = True)
- **AND** responde `200 OK`

#### Scenario: Verificar 2FA en login

- **WHEN** un usuario envía `POST /api/auth/2fa/verify` con un `session_token` de login y un código TOTP válido
- **THEN** el sistema emite un access token y un refresh token
- **AND** responde `200 OK` con el par de tokens

#### Scenario: Código TOTP inválido

- **WHEN** un usuario envía `POST /api/auth/2fa/verify` con un código TOTP inválido
- **THEN** el sistema responde `401 Unauthorized`

### Requirement: Deshabilitar 2FA

El sistema SHALL permitir a un usuario autenticado deshabilitar su propio 2FA mediante verificación de su contraseña actual.

#### Scenario: Deshabilitar 2FA exitosamente

- **WHEN** un usuario autenticado con 2FA activo envía `POST /api/auth/2fa/disable` con su contraseña actual válida
- **THEN** el sistema desactiva 2FA (totp_enabled = False) y elimina el secreto
- **AND** responde `204 No Content`

#### Scenario: Deshabilitar 2FA con contraseña incorrecta

- **WHEN** un usuario autenticado envía `POST /api/auth/2fa/disable` con una contraseña incorrecta
- **THEN** el sistema responde `401 Unauthorized`
