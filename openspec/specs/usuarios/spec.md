## ADDED Requirements

### Requirement: Gestión de usuarios extendidos con PII
El sistema SHALL exponer endpoints CRUD protegidos en `/api/admin/usuarios` para que usuarios con permiso `usuarios:*` administren los datos extendidos de usuarios del tenant, incluyendo PII (datos personales, impositivos, bancarios) cifrada con AES-256-GCM en reposo.

#### Scenario: Crear usuario exitosamente
- **WHEN** un usuario con permiso `usuarios:create` envía `POST /api/admin/usuarios` con `email, password, display_name, nombre, apellidos, dni, cuil`
- **THEN** el sistema SHALL crear el usuario, cifrar PII con AES-256-GCM, y devolver 201 con los datos del usuario (PII desencriptada en la respuesta)

#### Scenario: Crear usuario con email duplicado
- **WHEN** un usuario envía `POST /api/admin/usuarios` con un `email` que ya existe para el mismo tenant
- **THEN** el sistema SHALL devolver 409 Conflict

#### Scenario: Crear usuario sin permiso
- **WHEN** un usuario SIN permiso `usuarios:create` intenta crear un usuario
- **THEN** el sistema SHALL devolver 403 Forbidden

#### Scenario: Listar usuarios del tenant
- **WHEN** un usuario con permiso `usuarios:list` envía `GET /api/admin/usuarios`
- **THEN** el sistema SHALL devolver 200 con lista paginada de usuarios del tenant, incluyendo nombre, apellidos, email (últimos 4 chars visibles), legajo, estado, rol principal

#### Scenario: Listar usuarios con filtro por estado
- **WHEN** un usuario envía `GET /api/admin/usuarios?estado=inactivo`
- **THEN** el sistema SHALL devolver solo los usuarios con `estado = "inactivo"`

#### Scenario: Obtener usuario por ID con PII completa
- **WHEN** un usuario con permiso `usuarios:list` envía `GET /api/admin/usuarios/{id}`
- **THEN** el sistema SHALL devolver 200 con datos completos del usuario, incluyendo PII desencriptada (dni, cuil, cbu, alias_cbu, banco, email completo)

#### Scenario: Obtener usuario inexistente
- **WHEN** un usuario envía `GET /api/admin/usuarios/{id}` con un ID que no existe
- **THEN** el sistema SHALL devolver 404

#### Scenario: Obtener usuario de otro tenant
- **WHEN** un usuario envía `GET /api/admin/usuarios/{id}` con un ID de usuario de otro tenant
- **THEN** el sistema SHALL devolver 404 (aislamiento multi-tenant)

#### Scenario: Actualizar datos de usuario
- **WHEN** un usuario con permiso `usuarios:update` envía `PATCH /api/admin/usuarios/{id}` con `nombre`, `cbu`, `banco` actualizados
- **THEN** el sistema SHALL actualizar los campos, cifrar PII recibida, y devolver 200 con datos completos

#### Scenario: Actualizar email con nuevo valor único
- **WHEN** un usuario con permiso `usuarios:update` envía `PATCH /api/admin/usuarios/{id}` con un `email` nuevo que no existe en el tenant
- **THEN** el sistema SHALL actualizar el email (cifrado + hash) y devolver 200

#### Scenario: Actualizar email con valor duplicado
- **WHEN** un usuario envía `PATCH /api/admin/usuarios/{id}` con un `email` que ya pertenece a otro usuario del mismo tenant
- **THEN** el sistema SHALL devolver 409 Conflict

#### Scenario: Desactivar usuario (estado inactivo)
- **WHEN** un usuario con permiso `usuarios:update` envía `PATCH /api/admin/usuarios/{id}` con `estado: "inactivo"`
- **THEN** el sistema SHALL marcar el usuario como inactivo y devolver 200

### Requirement: Aislamiento multi-tenant en usuarios
El sistema SHALL garantizar que un administrador de tenant A no pueda ver, crear ni modificar usuarios del tenant B.

#### Scenario: Listar usuarios solo del propio tenant
- **WHEN** un ADMIN del tenant A lista usuarios
- **THEN** el sistema SHALL devolver solo usuarios con `tenant_id = A`

#### Scenario: Unicidad de email por tenant
- **WHEN** dos tenants distintos crean usuarios con el mismo email
- **THEN** ambas creaciones SHALL ser exitosas (el email es único dentro del tenant, no global)
