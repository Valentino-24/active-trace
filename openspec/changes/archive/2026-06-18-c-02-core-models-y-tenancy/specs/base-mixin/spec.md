## ADDED Requirements

### Requirement: Mixin base con UUID

Toda entidad del dominio SHALL heredar de un mixin que provea un identificador UUID como clave primaria.

#### Scenario: UUID autogenerado

- **WHEN** una nueva entidad es creada
- **THEN** el sistema asigna un UUID como su identificador
- **AND** el UUID es único a nivel global

### Requirement: Tenant ID en toda entidad

Toda entidad del dominio SHALL incluir `tenant_id` como clave foránea a la entidad Tenant.

#### Scenario: Tenant asignado en creación

- **WHEN** una nueva entidad es creada con un tenant_id
- **THEN** el campo tenant_id se persiste correctamente
- **AND** la entidad queda asociada al tenant correspondiente

### Requirement: Timestamps automáticos

Toda entidad del dominio SHALL incluir `created_at` y `updated_at` con valores asignados automáticamente por la base de datos.

#### Scenario: Timestamp de creación

- **WHEN** una nueva entidad es creada
- **THEN** `created_at` contiene la fecha/hora de creación

#### Scenario: Timestamp de actualización

- **WHEN** una entidad existente es modificada
- **THEN** `updated_at` se actualiza automáticamente

### Requirement: Soft delete

Toda entidad del dominio SHALL soportar soft delete mediante un campo `deleted_at`.

#### Scenario: Soft delete marca como eliminado

- **WHEN** una entidad es eliminada
- **THEN** el campo `deleted_at` se setea con la fecha/hora actual
- **AND** el registro no se elimina físicamente de la base de datos
- **AND** la entidad puede ser recuperada restaurando `deleted_at` a NULL

#### Scenario: Consulta excluye borrados

- **WHEN** se consulta una lista de entidades
- **THEN** las entidades con `deleted_at` no NULL NO son incluidas por defecto
