## ADDED Requirements

### Requirement: Repository genérico con scope de tenant

El sistema SHALL proveer un repositorio base genérico que aplique filtro por `tenant_id` en TODAS las consultas.

#### Scenario: Filtro automático por tenant

- **WHEN** el repository ejecuta `list()` o `get()`
- **THEN** todas las consultas incluyen el filtro `WHERE tenant_id = :tenant_id`

#### Scenario: Crear registro con tenant

- **WHEN** se crea un registro vía `create()` en el repository
- **THEN** el `tenant_id` del registro se asigna automáticamente desde el tenant del repository

#### Scenario: Soft delete vía repository

- **WHEN** se ejecuta `soft_delete()` en el repository
- **THEN** el registro recibe `deleted_at` en lugar de ser eliminado
- **AND** `get()` retorna `None` para registros eliminados

### Requirement: Consulta personalizada con tenant scope

Las subclases del repository base SHALL poder agregar filtros adicionales manteniendo el scope de tenant.

#### Scenario: Filtro adicional con tenant

- **WHEN** una subclase agrega un filtro adicional a la consulta base
- **THEN** la consulta resultante incluye tanto el filtro de tenant como el filtro adicional
