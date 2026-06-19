## ADDED Requirements

### Requirement: Administrar dictados
El sistema SHALL permitir a los usuarios con permiso `estructura:gestionar` administrar los dictados del tenant mediante operaciones CRUD sobre el recurso `/api/admin/dictados`. Un dictado SHALL representar la instancia de una materia del catálogo en una combinación `carrera × cohorte` concreta.

#### Scenario: Crear dictado exitosamente
- **WHEN** un usuario con permiso `estructura:gestionar` envía `POST /api/admin/dictados` con `materia_id`, `carrera_id`, `cohorte_id` válidos
- **THEN** el sistema SHALL crear el dictado y devolver 201 con `id`, `materia_id`, `carrera_id`, `cohorte_id`, `estado` (default "activo"), `created_at`, `updated_at`

#### Scenario: Crear dictado con materia inactiva
- **WHEN** un usuario envía `POST /api/admin/dictados` con un `materia_id` de una materia inactiva
- **THEN** el sistema SHALL devolver 400

#### Scenario: Crear dictado con carrera inactiva
- **WHEN** un usuario envía `POST /api/admin/dictados` con un `carrera_id` de una carrera inactiva
- **THEN** el sistema SHALL devolver 400

#### Scenario: Crear dictado duplicado
- **WHEN** un usuario envía `POST /api/admin/dictados` con una combinación `(materia_id, carrera_id, cohorte_id)` que ya existe
- **THEN** el sistema SHALL devolver 409 Conflict

#### Scenario: Cerrar dictado
- **WHEN** un usuario envía `PUT /api/admin/dictados/{id}` con `estado: "inactivo"`
- **THEN** el sistema SHALL marcar el dictado como inactivo y devolver 200

#### Scenario: Listar dictados por materia o cohorte
- **WHEN** un usuario envía `GET /api/admin/dictados` con `materia_id` o `cohorte_id` como query params
- **THEN** el sistema SHALL devolver 200 con los dictados filtrados del tenant (paginada)

#### Scenario: Validar aislamiento multi-tenant en dictados
- **WHEN** un usuario de tenant A consulta un dictado del tenant B por ID
- **THEN** el sistema SHALL devolver 404
