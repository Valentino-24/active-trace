## ADDED Requirements

### Requirement: Administrar carreras
El sistema SHALL permitir a los usuarios con permiso `estructura:gestionar` administrar las carreras del tenant mediante operaciones CRUD sobre el recurso `/api/admin/carreras`.

#### Scenario: Crear carrera exitosamente
- **WHEN** un usuario con permiso `estructura:gestionar` envía `POST /api/admin/carreras` con `codigo` y `nombre` válidos
- **THEN** el sistema SHALL crear la carrera y devolver 201 con los datos completos incluyendo `id`, `codigo`, `nombre`, `estado` (default "activa"), `created_at`, `updated_at`

#### Scenario: Crear carrera con código duplicado
- **WHEN** un usuario envía `POST /api/admin/carreras` con un `codigo` que ya existe para el mismo tenant
- **THEN** el sistema SHALL devolver 409 Conflict

#### Scenario: Crear carrera con código duplicado en otro tenant
- **WHEN** dos tenants distintos crean carreras con el mismo `codigo`
- **THEN** ambas creaciones SHALL ser exitosas (la unicidad es por tenant)

#### Scenario: Listar carreras
- **WHEN** un usuario envía `GET /api/admin/carreras`
- **THEN** el sistema SHALL devolver 200 con la lista de carreras del tenant (paginada)

#### Scenario: Obtener carrera por ID
- **WHEN** un usuario envía `GET /api/admin/carreras/{id}`
- **THEN** el sistema SHALL devolver 200 con los datos de la carrera

#### Scenario: Obtener carrera inexistente
- **WHEN** un usuario envía `GET /api/admin/carreras/{id}` con un ID que no existe
- **THEN** el sistema SHALL devolver 404

#### Scenario: Obtener carrera de otro tenant
- **WHEN** un usuario envía `GET /api/admin/carreras/{id}` con un ID de carrera de otro tenant
- **THEN** el sistema SHALL devolver 404 (aislamiento multi-tenant)

#### Scenario: Actualizar carrera
- **WHEN** un usuario envía `PUT /api/admin/carreras/{id}` con `codigo` y `nombre` actualizados
- **THEN** el sistema SHALL actualizar la carrera y devolver 200 con los datos modificados

#### Scenario: Cambiar estado de carrera a inactiva
- **WHEN** un usuario envía `PUT /api/admin/carreras/{id}` con `estado: "inactiva"`
- **THEN** el sistema SHALL marcar la carrera como inactiva y devolver 200

#### Scenario: Crear cohorte en carrera inactiva
- **WHEN** un usuario intenta crear una cohorte para una carrera con `estado: "inactiva"`
- **THEN** el sistema SHALL devolver 400 con el mensaje "La carrera está inactiva"

#### Scenario: Soft-delete carrera
- **WHEN** un usuario envía `DELETE /api/admin/carreras/{id}`
- **THEN** el sistema SHALL soft-delete la carrera (ocultarla de listados, conservarla en BD)
