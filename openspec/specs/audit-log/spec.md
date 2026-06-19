## ADDED Requirements

### Requirement: Sistema de auditoría append-only
El sistema SHALL mantener un registro de auditoría inmutable para todas las acciones significativas. Un registro de auditoría NO puede ser modificado ni eliminado una vez creado.

#### Scenario: Crear registro de auditoría exitoso
- **WHEN** un usuario autenticado realiza una acción significativa (ej: importar calificaciones)
- **THEN** el sistema SHALL crear un registro en el audit log con actor_id = user.id, accion = "CALIFICACIONES_IMPORTAR", fecha_hora = timestamp actual, filas_afectadas >= 0

#### Scenario: Rechazar actualización de registro de auditoría
- **WHEN** un usuario intenta modificar un registro existente del audit log
- **THEN** la base de datos SHALL rechazar la operación (error a nivel de base de datos)

#### Scenario: Rechazar eliminación de registro de auditoría
- **WHEN** un usuario intenta eliminar un registro del audit log
- **THEN** la base de datos SHALL rechazar la operación (error a nivel de base de datos)

### Requirement: Campos del registro de auditoría
Cada registro de auditoría SHALL contener los campos definidos en E-AUD:
- id (UUID, PK)
- tenant_id (UUID, FK → Tenant)
- fecha_hora (datetime with timezone)
- actor_id (UUID, FK → Usuario, quien realizó la acción)
- impersonado_id (UUID, FK → Usuario, nullable — solo si hay impersonación activa)
- materia_id (UUID, FK → Materia, nullable)
- accion (text, código estandarizado como "CALIFICACIONES_IMPORTAR")
- detalle (JSON con contexto adicional de la acción)
- filas_afectadas (entero, cantidad de registros involucrados)
- ip (text, dirección IP del cliente)
- user_agent (text, agente de usuario)

#### Scenario: Crear registro completo con todos los campos
- **WHEN** se registra una importación de calificaciones con todos los datos disponibles
- **THEN** el registro SHALL contener: id generado, tenant_id del actor, fecha_hora actual, actor_id, accion = "CALIFICACIONES_IMPORTAR", detalle con datos relevantes, filas_afectadas = N, ip del cliente, user_agent

#### Scenario: Crear registro sin impersonado_id
- **WHEN** una acción es realizada por un usuario autenticado sin impersonación activa
- **THEN** el campo impersonado_id SHALL ser NULL

### Requirement: Códigos de acción estandarizados
Las acciones del audit log SHALL usar códigos textuales estandarizados con formato `MODULO_ACCION` (ej: `CALIFICACIONES_IMPORTAR`, `COMUNICACION_ENVIAR`, `IMPERSONACION_INICIAR`).

#### Scenario: Usar código de acción estandarizado
- **WHEN** se crea un registro de auditoría para una comunicación enviada
- **THEN** el campo accion SHALL ser "COMUNICACION_ENVIAR"

### Requirement: Helper de auditoría log_action()
El sistema SHALL proveer una función `log_action()` que centralice la creación de registros de auditoría. Debe aceptar: db, tenant_id, actor_id, accion, detalle (dict, opcional), filas_afectadas (int, default 1), materia_id (UUID, opcional), impersonado_id (UUID, opcional), ip (str, opcional), user_agent (str, opcional).

#### Scenario: Usar helper con contexto mínimo
- **WHEN** se llama a `log_action(db, tenant_id=..., actor_id=..., accion="CALIFICACIONES_IMPORTAR")`
- **THEN** se crea un registro con todos los campos requeridos y opcionales en NULL o default

#### Scenario: Usar helper con todos los parámetros
- **WHEN** se llama a `log_action(...)` con detalle, filas_afectadas, materia_id, ip, user_agent
- **THEN** el registro incluye todos esos valores correctamente

### Requirement: Captura de contexto de request (IP y User-Agent)
El helper `log_action()` SHALL aceptar opcionalmente un objeto `Request` de FastAPI y extraer automáticamente `request.client.host` como ip y `request.headers.get("user-agent")` como user_agent.

#### Scenario: Extraer IP y user-agent del request
- **WHEN** se pasa `request` a `log_action()`
- **THEN** ip = request.client.host y user_agent = request.headers.get("user-agent")

#### Scenario: No sobrescribir IP si se pasa explícitamente
- **WHEN** se pasa tanto `request` como `ip` explícitamente a `log_action()`
- **THEN** se usa el valor explícito de `ip`, no el del request
