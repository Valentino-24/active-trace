## ADDED Requirements

### Requirement: Catálogo de roles administrable

El sistema SHALL mantener un catálogo de roles administrable por tenant. Cada rol SHALL tener un nombre, un código único (e.g. "PROFESOR") y una descripción. Los roles NO SHALL estar hardcodeados en el código.

#### Scenario: Crear un rol

- **WHEN** un usuario con permiso de administración crea un rol con nombre, código y descripción
- **THEN** el rol se persiste en la tabla `role` con un UUID único

#### Scenario: Código de rol duplicado en el mismo tenant

- **WHEN** se intenta crear un rol con un código que ya existe dentro del mismo tenant
- **THEN** el sistema rechaza la operación con error de unique constraint

### Requirement: Catálogo de permisos administrable

El sistema SHALL mantener un catálogo de permisos administrable por tenant. Cada permiso SHALL tener un código en formato `modulo:accion` (e.g. "calificaciones:importar") único por tenant y una descripción.

#### Scenario: Crear un permiso

- **WHEN** un usuario con permiso de administración crea un permiso con código y descripción
- **THEN** el permiso se persiste en la tabla `permission` con un UUID único

### Requirement: Matriz rol × permiso

El sistema SHALL mantener una matriz N:N que asocie permisos a roles. Un rol puede tener múltiples permisos y un permiso puede estar asignado a múltiples roles.

#### Scenario: Asignar permiso a rol

- **WHEN** un usuario con permiso de administración asigna un permiso existente a un rol existente
- **THEN** la relación se persiste en la tabla `role_permission`

#### Scenario: Asignación duplicada

- **WHEN** se intenta asignar el mismo permiso al mismo rol dos veces
- **THEN** el sistema rechaza la operación con error de unique constraint

### Requirement: Asignación de roles a usuarios con vigencia

El sistema SHALL permitir asignar uno o más roles a un usuario, cada uno con una fecha de inicio (`desde`) y una fecha de fin opcional (`hasta`). Una asignación SHALL estar vigente si la fecha actual está dentro del rango `[desde, hasta)`.

#### Scenario: Asignar rol a usuario

- **WHEN** un usuario con permiso de administración asigna un rol a un usuario con fecha de inicio y sin fecha de fin
- **THEN** la asignación se persiste en la tabla `user_role`

#### Scenario: Asignación vigente

- **WHEN** se consultan los permisos de un usuario y tiene una asignación de rol con `desde` en el pasado y `hasta` NULL
- **THEN** los permisos de ese rol se incluyen en los permisos efectivos del usuario

#### Scenario: Asignación vencida

- **WHEN** se consultan los permisos de un usuario y tiene una asignación de rol con `hasta` en el pasado
- **THEN** los permisos de ese rol NO se incluyen en los permisos efectivos del usuario

### Requirement: Guard require_permission para endpoints

El sistema SHALL proveer una dependency `require_permission(permiso: str)` que verifique que el usuario autenticado tiene el permiso especificado. Si no lo tiene, SHALL responder `403 Forbidden`.

#### Scenario: Usuario con permiso

- **WHEN** un usuario autenticado con el permiso `calificaciones:importar` accede a un endpoint protegido con `require_permission("calificaciones:importar")`
- **THEN** el endpoint ejecuta normalmente

#### Scenario: Usuario sin permiso

- **WHEN** un usuario autenticado SIN el permiso `calificaciones:importar` accede a un endpoint protegido con `require_permission("calificaciones:importar")`
- **THEN** el sistema responde `403 Forbidden`

#### Scenario: Usuario no autenticado

- **WHEN** un usuario no autenticado accede a un endpoint protegido con `require_permission`
- **THEN** el sistema responde `401 Unauthorized` (el guard de auth se ejecuta antes)

### Requirement: Resolución de permisos efectivos por request

El sistema SHALL calcular los permisos efectivos de un usuario en cada request como la unión de los permisos de todos sus roles vigentes (asignaciones activas a la fecha actual), acotados por su tenant.

#### Scenario: Unión de roles

- **WHEN** un usuario tiene dos roles vigentes, uno con permiso A y otro con permiso B
- **THEN** los permisos efectivos del usuario incluyen tanto A como B

#### Scenario: Sin roles asignados

- **WHEN** un usuario autenticado no tiene ningún rol asignado
- **THEN** sus permisos efectivos son un conjunto vacío
- **AND** cualquier `require_permission` responde `403 Forbidden`

### Requirement: Seed inicial de roles y permisos

El sistema SHALL incluir un seed inicial con los 7 roles del dominio y la matriz de permisos definida en la documentación del producto (`03_actores_y_roles.md §3.3`).

#### Scenario: Roles seed creados

- **WHEN** se ejecuta la migración 003 por primera vez
- **THEN** se crean los roles ALUMNO, TUTOR, PROFESOR, COORDINADOR, NEXO, ADMIN, FINANZAS
- **AND** se crean los permisos definidos en la matriz de capacidades
- **AND** se crean las relaciones role_permission correspondientes
