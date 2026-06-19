## ADDED Requirements

### Requirement: Gestión de asignaciones usuario-rol-contexto
El sistema SHALL exponer endpoints en `/api/asignaciones` para que usuarios con permiso `equipos:asignar` y `equipos:revocar` administren las asignaciones de usuarios a roles dentro de un contexto académico (materia, carrera, cohorte, comisiones) con vigencia temporal.

#### Scenario: Crear asignación exitosamente
- **WHEN** un usuario con permiso `equipos:asignar` envía `POST /api/asignaciones` con `usuario_id, rol, materia_id, carrera_id, cohorte_id, desde` válidos
- **THEN** el sistema SHALL crear la asignación con `estado_vigencia: "vigente"` y devolver 201 con los datos completos

#### Scenario: Crear asignación con responsable
- **WHEN** un usuario envía `POST /api/asignaciones` con `responsable_id` válido
- **THEN** el sistema SHALL crear la asignación con el responsable vinculado

#### Scenario: Crear asignación sin permiso
- **WHEN** un usuario SIN permiso `equipos:asignar` intenta crear una asignación
- **THEN** el sistema SHALL devolver 403 Forbidden

#### Scenario: Crear asignación con usuario de otro tenant
- **WHEN** un usuario envía `POST /api/asignaciones` con un `usuario_id` que pertenece a otro tenant
- **THEN** el sistema SHALL devolver 404 (el usuario no existe para este tenant)

#### Scenario: Crear asignación con materia de otro tenant
- **WHEN** un usuario envía `POST /api/asignaciones` con un `materia_id` que pertenece a otro tenant
- **THEN** el sistema SHALL devolver 404

#### Scenario: Revocar asignación (fin de vigencia)
- **WHEN** un usuario con permiso `equipos:revocar` envía `DELETE /api/asignaciones/{id}`
- **THEN** el sistema SHALL establecer `hasta = today` y devolver 200 con la asignación actualizada y `estado_vigencia: "vencida"`

#### Scenario: Revocar asignación ya vencida
- **WHEN** un usuario envía `DELETE /api/asignaciones/{id}` sobre una asignación ya vencida
- **THEN** el sistema SHALL devolver 200 (idempotente — no cambia nada)

#### Scenario: Revocar asignación inexistente
- **WHEN** un usuario envía `DELETE /api/asignaciones/{id}` con un ID que no existe
- **THEN** el sistema SHALL devolver 404

### Requirement: Listado y filtros de asignaciones
El sistema SHALL exponer `GET /api/asignaciones` para que usuarios con permiso `equipos:asignar` consulten las asignaciones del tenant con filtros.

#### Scenario: Listar asignaciones activas
- **WHEN** un usuario con permiso `equipos:asignar` envía `GET /api/asignaciones`
- **THEN** el sistema SHALL devolver 200 con lista paginada de asignaciones activas del tenant

#### Scenario: Filtrar por materia
- **WHEN** un usuario envía `GET /api/asignaciones?materia_id=...`
- **THEN** el sistema SHALL devolver solo asignaciones de esa materia

#### Scenario: Filtrar por usuario
- **WHEN** un usuario envía `GET /api/asignaciones?usuario_id=...`
- **THEN** el sistema SHALL devolver solo asignaciones de ese usuario

#### Scenario: Filtrar por rol
- **WHEN** un usuario envía `GET /api/asignaciones?rol=PROFESOR`
- **THEN** el sistema SHALL devolver solo asignaciones con ese rol

#### Scenario: Incluir vencidas con filtro
- **WHEN** un usuario envía `GET /api/asignaciones?incluir_vencidas=true`
- **THEN** el sistema SHALL incluir asignaciones vencidas en el resultado

### Requirement: Vigencia y estado derivado
El sistema SHALL derivar `estado_vigencia` de las fechas `desde` y `hasta` sin almacenarlo en BD.

#### Scenario: Asignación vigente sin fecha fin
- **GIVEN** una asignación con `hasta = NULL` y `desde <= today`
- **THEN** `estado_vigencia` SHALL ser `"vigente"`

#### Scenario: Asignación vigente con fecha futura
- **GIVEN** una asignación con `hasta >= today` y `desde <= today`
- **THEN** `estado_vigencia` SHALL ser `"vigente"`

#### Scenario: Asignación vencida
- **GIVEN** una asignación con `hasta < today`
- **THEN** `estado_vigencia` SHALL ser `"vencida"`

#### Scenario: Asignación futura (no vigente aún)
- **GIVEN** una asignación con `desde > today`
- **THEN** `estado_vigencia` SHALL ser `"pendiente"`
