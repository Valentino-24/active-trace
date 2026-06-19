## ADDED Requirements

### Requirement: Endpoint de inicio de impersonación
El sistema SHALL exponer `POST /api/v1/auth/impersonate/start` para que un usuario con permiso `impersonacion:usar` pueda iniciar una sesión de impersonación sobre otro usuario activo del mismo tenant.

#### Scenario: Iniciar impersonación exitosamente
- **WHEN** un usuario con permiso `impersonacion:usar` envía POST a `/api/v1/auth/impersonate/start` con `{"user_id": "<uuid>"}` de un usuario activo del mismo tenant
- **THEN** el sistema SHALL devolver 200 OK con un `impersonation_token` (JWT) y `access_token` (nuevo JWT para la sesión impersonada)
- **AND** SHALL crear un registro en audit_log con accion = "IMPERSONACION_INICIAR", actor_id = impersonator, impersonado_id = usuario impersonado

#### Scenario: Rechazar impersonación sin permiso
- **WHEN** un usuario SIN permiso `impersonacion:usar` intenta iniciar impersonación
- **THEN** el sistema SHALL devolver 403 Forbidden

#### Scenario: Rechazar impersonación de usuario inexistente
- **WHEN** un usuario con permiso `impersonacion:usar` intenta impersonar un user_id que no existe
- **THEN** el sistema SHALL devolver 404 Not Found

#### Scenario: Rechazar impersonación de usuario inactivo
- **WHEN** un usuario con permiso `impersonacion:usar` intenta impersonar un usuario inactivo (is_active = False)
- **THEN** el sistema SHALL devolver 400 Bad Request con detalle explicativo

#### Scenario: Rechazar impersonación de otro tenant
- **WHEN** un usuario intenta impersonar un usuario de otro tenant
- **THEN** el sistema SHALL devolver 404 Not Found (no revelar existencia del usuario)

### Requirement: Endpoint de fin de impersonación
El sistema SHALL exponer `POST /api/v1/auth/impersonate/end` para finalizar una sesión de impersonación activa y restaurar la sesión original del impersonator.

#### Scenario: Finalizar impersonación exitosamente
- **WHEN** un usuario bajo impersonación envía POST a `/api/v1/auth/impersonate/end`
- **THEN** el sistema SHALL devolver 200 OK con un nuevo `access_token` para la sesión original del impersonator
- **AND** SHALL crear un registro en audit_log con accion = "IMPERSONACION_FINALIZAR", actor_id = impersonator, impersonado_id = usuario impersonado

#### Scenario: Finalizar impersonación sin estar impersonando
- **WHEN** un usuario NO bajo impersonación envía POST a `/api/v1/auth/impersonate/end`
- **THEN** el sistema SHALL devolver 400 Bad Request

### Requirement: JWT distinguible bajo impersonación
Cuando un usuario está bajo impersonación, el JWT SHALL contener tanto `sub` (user_id del impersonado) como `impersonator_id` (user_id del actor real). El resto de claims (tenant_id, roles) corresponden al impersonado.

#### Scenario: JWT normal sin impersonación
- **WHEN** se genera un token para un login normal
- **THEN** el JWT contiene sub, tenant_id, roles, exp, iat, jti
- **AND** NO contiene el claim impersonator_id

#### Scenario: JWT bajo impersonación
- **WHEN** se inicia una impersonación exitosa
- **THEN** el JWT contiene sub (impersonado), impersonator_id (actor real), tenant_id (del impersonado), exp, iat, jti

### Requirement: get_current_user expone estado de impersonación
La dependencia `get_current_user` SHALL detectar automáticamente si el JWT tiene el claim `impersonator_id` y, en ese caso, cargar ambos usuarios. El User devuelto SHALL ser el impersonado (para que los endpoints operen sobre él), y SHALL exponer `is_impersonating = True`.

#### Scenario: get_current_user con token normal
- **WHEN** se pasa un JWT sin impersonator_id
- **THEN** get_current_user devuelve el User correspondiente
- **AND** user.is_impersonating = False

#### Scenario: get_current_user con token de impersonación
- **WHEN** se pasa un JWT con impersonator_id
- **THEN** get_current_user devuelve el User correspondiente al impersonado
- **AND** user.is_impersonating = True

#### Scenario: roles y permisos bajo impersonación
- **WHEN** get_current_user resuelve un usuario bajo impersonación
- **THEN** los roles y permisos SHALL ser los del impersonado (el usuario efectivo), no del impersonator
