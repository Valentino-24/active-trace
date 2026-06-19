## ADDED Requirements

### Requirement: Administrar materias (catálogo)
El sistema SHALL permitir a los usuarios con permiso `estructura:gestionar` administrar el catálogo único de materias del tenant mediante operaciones CRUD sobre el recurso `/api/admin/materias`.

#### Scenario: Crear materia exitosamente
- **WHEN** un usuario con permiso `estructura:gestionar` envía `POST /api/admin/materias` con `codigo` y `nombre` válidos
- **THEN** el sistema SHALL crear la materia y devolver 201 con `id`, `codigo`, `nombre`, `estado` (default "activa"), `created_at`, `updated_at`

#### Scenario: Crear materia con código duplicado
- **WHEN** un usuario envía `POST /api/admin/materias` con un `codigo` que ya existe para el mismo tenant
- **THEN** el sistema SHALL devolver 409 Conflict

#### Scenario: Listar materias
- **WHEN** un usuario envía `GET /api/admin/materias`
- **THEN** el sistema SHALL devolver 200 con la lista de materias del tenant (paginada)

#### Scenario: Desactivar materia
- **WHEN** un usuario envía `PUT /api/admin/materias/{id}` con `estado: "inactiva"`
- **THEN** el sistema SHALL marcar la materia como inactiva y devolver 200

#### Scenario: Crear dictado con materia inactiva
- **WHEN** un usuario intenta crear un dictado para una materia con `estado: "inactiva"`
- **THEN** el sistema SHALL devolver 400 con el mensaje "La materia está inactiva"

## ADDED Requirements (C-18 Liquidaciones)

### Requirement: Grupo Plus en Materia
El sistema SHALL permitir asignar un `grupo_plus` opcional a cada materia para el cálculo de liquidaciones. Este campo es configurable por tenant, nullable, y se utiliza para agrupar materias en el cálculo de plus salariales.

#### Scenario: Materia con grupo_plus
- **WHEN** un ADMIN crea o modifica una materia con `grupo_plus: "PROG"`
- **THEN** la materia queda asociada al grupo PROG para liquidaciones

#### Scenario: Materia sin grupo_plus
- **WHEN** una materia tiene `grupo_plus: null`
- **THEN** no genera plus salarial en el cálculo de liquidaciones
