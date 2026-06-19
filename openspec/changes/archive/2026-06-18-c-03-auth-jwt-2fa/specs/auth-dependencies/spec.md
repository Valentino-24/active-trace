## ADDED Requirements

### Requirement: Dependency get_current_user

El sistema SHALL proveer una dependency `get_current_user` que extraiga el token JWT del header `Authorization: Bearer <token>`, lo verifique y resuelva el usuario correspondiente desde la base de datos. El usuario resuelto SHALL estar disponible para los endpoints protegidos.

#### Scenario: Token JWT válido

- **WHEN** un endpoint protegido recibe una request con un JWT access token válido y no expirado en el header `Authorization`
- **THEN** `get_current_user` resuelve el `User` correspondiente al `sub` del token
- **AND** inyecta el usuario en el handler del endpoint

#### Scenario: Token JWT expirado

- **WHEN** un endpoint protegido recibe una request con un JWT access token expirado
- **THEN** `get_current_user` lanza `HTTPException 401`

#### Scenario: Token JWT inválido

- **WHEN** un endpoint protegido recibe una request con un JWT mal formado o firmado con una clave distinta
- **THEN** `get_current_user` lanza `HTTPException 401`

#### Scenario: Token válido pero usuario inactivo

- **WHEN** un endpoint protegido recibe una request con un JWT válido pero el usuario tiene `is_active = False`
- **THEN** `get_current_user` lanza `HTTPException 401`

#### Scenario: Token sin header Authorization

- **WHEN** un endpoint protegido recibe una request sin header `Authorization`
- **THEN** `get_current_user` lanza `HTTPException 403` (para no revelar autenticación requerida vs. autorización)

### Requirement: Identidad exclusivamente del JWT (regla de oro)

El sistema SHALL garantizar que la identidad del usuario (UUID, tenant, roles) se derive EXCLUSIVAMENTE del JWT verificado. Ningún parámetro de query string, body, header adicional ni cookie puede alterar la identidad del usuario autenticado.

#### Scenario: Intento de alterar identidad por parámetro

- **WHEN** un usuario autenticado envía una request a un endpoint protegido incluyendo un parámetro `user_id` o `tenant_id` en el body o query string
- **THEN** el endpoint ignora esos parámetros para efectos de identidad
- **AND** el endpoint opera con la identidad del JWT

#### Scenario: Impersonación no implementada falla por diseño

- **WHEN** un usuario intenta usar un header `X-Impersonate-As` para actuar como otro usuario
- **THEN** el sistema ignora ese header (la impersonación se implementará explícitamente en C-05 o change dedicado)
