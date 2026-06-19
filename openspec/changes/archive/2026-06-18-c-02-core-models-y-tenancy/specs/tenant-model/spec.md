## ADDED Requirements

### Requirement: Entidad Tenant

El sistema SHALL proveer una entidad `Tenant` que represente una institución. Todo registro de datos del dominio SHALL pertenecer a un tenant.

#### Scenario: Crear tenant

- **WHEN** un tenant es creado con nombre, código único y estado activo
- **THEN** el sistema persiste el tenant con un UUID como identificador
- **AND** los timestamps created_at y updated_at se setean automáticamente

#### Scenario: Código de tenant único

- **WHEN** se intenta crear un tenant con un código que ya existe
- **THEN** el sistema rechaza la operación por violación de unicidad

#### Scenario: Tenant inactivo

- **WHEN** un tenant se marca como inactivo
- **THEN** el sistema persiste el cambio sin borrar el registro
- **AND** las operaciones sobre datos de ese tenant deben manejarse según la regla de negocio correspondiente

### Requirement: Configuración por tenant

El modelo Tenant SHALL incluir un campo JSONB para almacenar configuración específica del tenant (plantillas, escalas, flags).

#### Scenario: Almacenar configuración

- **WHEN** se asigna configuración JSON a un tenant
- **THEN** el campo de configuración almacena y recupera el valor correctamente

### Requirement: Aislamiento multi-tenant

Los datos de un tenant NO SHALL ser accesibles desde las operaciones de otro tenant.

#### Scenario: Aislamiento en consulta

- **WHEN** el repository del tenant A ejecuta una consulta
- **THEN** los resultados NO incluyen registros del tenant B
