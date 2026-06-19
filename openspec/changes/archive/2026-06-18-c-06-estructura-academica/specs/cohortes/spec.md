## ADDED Requirements

### Requirement: Administrar cohortes
El sistema SHALL permitir a los usuarios con permiso `estructura:gestionar` administrar las cohortes del tenant mediante operaciones CRUD sobre el recurso `/api/admin/cohortes`. Una cohorte SHALL pertenecer a una carrera específica.

#### Scenario: Crear cohorte exitosamente
- **WHEN** un usuario con permiso `estructura:gestionar` envía `POST /api/admin/cohortes` con `carrera_id`, `nombre`, `anio`, `vig_desde` válidos
- **THEN** el sistema SHALL crear la cohorte y devolver 201 con `id`, `carrera_id`, `nombre`, `anio`, `vig_desde`, `vig_hasta` (default null = abierta), `estado` (default "activa")

#### Scenario: Crear cohorte con nombre duplicado en misma carrera
- **WHEN** un usuario envía `POST /api/admin/cohortes` con un `nombre` que ya existe para la misma `(tenant_id, carrera_id)`
- **THEN** el sistema SHALL devolver 409 Conflict

#### Scenario: Crear cohorte en carrera inexistente
- **WHEN** un usuario envía `POST /api/admin/cohortes` con un `carrera_id` que no existe
- **THEN** el sistema SHALL devolver 404

#### Scenario: Crear cohorte en carrera inactiva
- **WHEN** un usuario envía `POST /api/admin/cohortes` con un `carrera_id` de una carrera inactiva
- **THEN** el sistema SHALL devolver 400 con el mensaje "La carrera está inactiva"

#### Scenario: Listar cohortes filtradas por carrera
- **WHEN** un usuario envía `GET /api/admin/cohortes?carrera_id=...`
- **THEN** el sistema SHALL devolver 200 con las cohortes de esa carrera (paginada)

#### Scenario: Listar cohortes sin filtro
- **WHEN** un usuario envía `GET /api/admin/cohortes` sin filtros
- **THEN** el sistema SHALL devolver 200 con todas las cohortes del tenant (paginada)

#### Scenario: Cerra cohorte (vig_hasta)
- **WHEN** un usuario envía `PUT /api/admin/cohortes/{id}` con `vig_hasta` establecido
- **THEN** el sistema SHALL actualizar `vig_hasta` y cambiar `estado` a "inactiva"

#### Scenario: Validar aislamiento multi-tenant en cohortes
- **WHEN** un usuario de tenant A consulta una cohorte del tenant B por ID
- **THEN** el sistema SHALL devolver 404
