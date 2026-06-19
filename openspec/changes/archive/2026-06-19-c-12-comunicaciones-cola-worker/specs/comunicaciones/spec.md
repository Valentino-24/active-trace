# Comunicaciones Specification

> Gestión completa de comunicaciones salientes — preview con variables de sustitución, envío masivo asíncrono con cola, máquina de estados (RN-15), aprobación configurable por tenant, tracking por destinatario. Nuevo módulo que cierra el canal de comunicación saliente del sistema.

## Permisos

| Permiso | Descripción | Asignado a |
|---------|-------------|-----------|
| `comunicacion:enviar` | Crear y enviar comunicaciones | PROFESOR (scope propia asignación), COORDINADOR, ADMIN |
| `comunicacion:aprobar` | Aprobar o rechazar envíos masivos | COORDINADOR, ADMIN |

## ADDED Requirements

### R-COM-01 — Preview de comunicación (F3.1, RN-16)

The system SHALL render a preview of subject and body before enqueuing any communication. The preview SHALL show the final rendered text with all variables substituted per recipient. The user MUST confirm explicitly before enqueueing.

#### Scenario: Preview with valid variables renders personalized text

- GIVEN a template with subject "Recordatorio ${materia}" and body "Hola ${nombre} ${apellido}, tenés actividades pendientes en ${materia}"
- WHEN a PROFESOR requests preview for a specific alumno
- THEN the system returns the rendered subject "Recordatorio Programación I" and body "Hola Juan Pérez, tenés actividades pendientes en Programación I"

#### Scenario: Preview with unknown variable preserves placeholder

- GIVEN a template with subject "Notificación ${materia}" and body "Tu comisión es ${comision}" where `comision` is not a supported variable
- WHEN requesting preview
- THEN the rendered body contains "${comision}" as-is (no crash, no substitution)

#### Scenario: Preview with single recipient

- WHEN a PROFESOR requests preview for one alumno
- THEN the response contains one rendered version personalized for that alumno

#### Scenario: Preview with multiple recipients

- WHEN a PROFESOR requests preview for three alumnos
- THEN the response contains three rendered versions, each personalized with that recipient's data

#### Scenario: Preview without confirmation does not enqueue

- GIVEN a preview has been generated but no confirmation was sent
- WHEN no explicit confirmation is received
- THEN no Comunicacion record is created and no message is enqueued

### R-COM-02 — Envío masivo con cola (F3.2, RN-15)

The system SHALL create Comunicacion records in Pendiente state when a confirmed batch is submitted. Messages SHALL be grouped by `lote_id`. A worker SHALL process messages through Pendiente → Enviando → Enviado | Error. PROFESOR scope SHALL be limited to their own asignaciones. COORD/ADMIN scope SHALL include all messages in the tenant. An audit event `COMUNICACION_ENVIAR` SHALL be recorded.

#### Scenario: Successful batch enqueue creates all Pendiente with same lote_id

- GIVEN a batch of 5 confirmed recipients for materia X
- WHEN the user confirms the envío masivo
- THEN 5 Comunicacion records are created
- AND all records share the same `lote_id`
- AND all records have `estado: "Pendiente"`
- AND an audit event `COMUNICACION_ENVIAR` is recorded with the lote_id and recipient count

#### Scenario: Worker processes Pendiente messages to Enviado

- GIVEN a Comunicacion in Pendiente state with valid email address
- WHEN the worker picks it up
- THEN the message transitions to Enviando, then to Enviado
- AND `enviado_at` is set to the current timestamp

#### Scenario: Worker fails and marks Error

- GIVEN a Comunicacion in Pendiente state with an invalid email address
- WHEN the worker attempts to send and SMTP fails
- THEN the message transitions to Enviando, then to Error

#### Scenario: PROFESOR sends to own students — allowed

- GIVEN a PROFESOR with asignación A in materia X
- WHEN they send a communication to recipients from asignación A
- THEN all records are created successfully in Pendiente state

#### Scenario: PROFESOR cannot send to students of another asignación

- GIVEN a PROFESOR with asignación A in materia X, and recipients from asignación B
- WHEN they attempt to include recipients from asignación B
- THEN the request is rejected with 403 Forbidden

#### Scenario: COORDINADOR sends to any asignación — allowed

- GIVEN a COORDINADOR with scope over materia X
- WHEN they send a communication to recipients from any asignación in materia X
- THEN all records are created successfully in Pendiente state

### R-COM-03 — Aprobación de envíos masivos (F3.3, RN-17)

Messages SHALL remain in Pendiente until approved when the tenant flag `requiere_aprobacion_comunicaciones` is enabled. Only users with `comunicacion:aprobar` SHALL approve or reject. Approval SHALL work at lote level and at individual level. Approved messages SHALL transition to Enviando. Rejected or cancelled messages SHALL transition to Cancelado.

#### Scenario: Approve lote transitions all Pendiente to Enviando

- GIVEN a lote with 10 messages in Pendiente state and `requiere_aprobacion_comunicaciones` is enabled
- WHEN a user with `comunicacion:aprobar` approves the lote
- THEN all 10 messages transition to Enviando (worker picks them up)

#### Scenario: Approve individual message transitions only that message

- GIVEN a lote with 10 messages in Pendiente state
- WHEN a user with `comunicacion:aprobar` approves a single message
- THEN only that message transitions to Enviando; the other 9 remain Pendiente

#### Scenario: Cancel lote transitions all Pendiente to Cancelado

- GIVEN a lote with 10 messages in Pendiente state
- WHEN a user with `comunicacion:aprobar` cancels the lote
- THEN all 10 messages transition to Cancelado

#### Scenario: Reject lote transitions all to Cancelado

- GIVEN a lote with 10 messages in Pendiente state
- WHEN a user with `comunicacion:aprobar` rejects the lote
- THEN all 10 messages transition to Cancelado

#### Scenario: User without `comunicacion:aprobar` receives 403

- GIVEN a PROFESOR (without `comunicacion:aprobar`) tries to approve a lote
- WHEN they call the approval endpoint
- THEN the response is 403 Forbidden

#### Scenario: Tenant with approval disabled auto-approves

- GIVEN `requiere_aprobacion_comunicaciones` is false for the tenant
- WHEN a confirmed batch is submitted
- THEN messages go directly to Enviando (bypass approval)
- AND they are processed by the worker immediately

### R-COM-04 — Máquina de estados (RN-15)

Messages SHALL follow the state machine: Pendiente → Enviando → Enviado | Error | Cancelado. NO transitions SHALL be allowed from terminal states (Enviado, Error, Cancelado). Cancel SHALL only work from Pendiente state.

#### Scenario: Happy path Pendiente → Enviando → Enviado

- GIVEN a Comunicacion in Pendiente state
- WHEN the worker processes it successfully
- THEN the message transitions to Enviando, then to Enviado

#### Scenario: User cancels from Pendiente

- GIVEN a Comunicacion in Pendiente state (not yet picked up by worker)
- WHEN a user with `comunicacion:aprobar` cancels it
- THEN it transitions to Cancelado

#### Scenario: Worker fails Pendiente → Enviando → Error

- GIVEN a Comunicacion in Pendiente state
- WHEN the worker attempts to send and the SMTP call fails
- THEN the message transitions to Enviando, then to Error

#### Scenario: Cannot cancel from Enviado (terminal state)

- GIVEN a Comunicacion in Enviado state
- WHEN a user attempts to cancel it
- THEN the request is rejected (error 409 or similar)
- AND the message remains Enviado

#### Scenario: Cannot transition from Cancelado

- GIVEN a Comunicacion in Cancelado state
- WHEN an attempt is made to transition it to Enviando
- THEN the transition is blocked
- AND the message remains Cancelado

#### Scenario: Cannot transition from Error

- GIVEN a Comunicacion in Error state
- WHEN an attempt is made to transition it to Enviado
- THEN the transition is blocked
- AND the message remains Error

### R-COM-05 — Template engine

The system SHALL support variable substitution in subject and body using `${variable}` syntax. Supported variables SHALL include: `nombre`, `apellido`, `materia`, `comision`, `nombre_profesor`. Unknown variables SHALL be left as-is (no crash).

#### Scenario: Template with all known variables correctly substituted

- GIVEN a template "${nombre} ${apellido}, tu materia ${materia} (comisión ${comision}) — ${nombre_profesor}"
- WHEN rendered for a specific alumno and profesor
- THEN the output is "Juan Pérez, tu materia Programación I (comisión A) — Dr. García"

#### Scenario: Template with unknown variable left as-is

- GIVEN a template "Hola ${nombre}, tu ${carrera} es correcta" where `carrera` is not supported
- WHEN rendered
- THEN the output is "Hola Juan, tu ${carrera} es correcta" (no crash, no error)

#### Scenario: Empty template renders empty string

- GIVEN a template with empty subject and empty body
- WHEN rendered
- THEN the output is an empty string for both subject and body

#### Scenario: Partial variable substitution

- GIVEN a template "Hola ${nombre}, tu materia es ${materia}"
- WHEN rendered for a recipient with only `nombre` populated (no `materia` context)
- THEN `nombre` is substituted and `materia` is left as "${materia}"

### R-COM-06 — Tracking y estadísticas

The system SHALL expose counts by estado per materia, and per-lote status detail. PROFESOR SHALL only see their own messages' stats. COORDINADOR and ADMIN SHALL see global stats.

#### Scenario: Query stats for materia returns grouped counts

- GIVEN materia X has 10 messages total: 3 Enviado, 2 Error, 4 Pendiente, 1 Cancelado
- WHEN a COORDINADOR queries stats for materia X
- THEN the response returns `{pendientes: 4, enviados: 3, fallidos: 2, cancelados: 1}`

#### Scenario: Query lote detail returns messages with their states

- GIVEN a lote with 5 messages in various states
- WHEN a user queries lote detail by lote_id
- THEN the response returns a list of 5 messages each with its current estado, destinatario metadata (not email), and timestamps

#### Scenario: PROFESOR sees only own materia stats

- GIVEN a PROFESOR with asignación A in materia X, and materia X also has messages from asignación B
- WHEN the PROFESOR queries stats for materia X
- THEN the response only includes counts for messages sent by the PROFESOR (asignación A)
- AND messages from asignación B are excluded

#### Scenario: Empty materia returns all zeros

- GIVEN materia Y with no Comunicacion records
- WHEN a user queries stats for materia Y
- THEN the response returns `{pendientes: 0, enviados: 0, fallidos: 0, cancelados: 0}`

### R-COM-07 — Destinatario cifrado

Email addresses SHALL be encrypted at rest using AES-256. Email SHALL NOT appear in logs or API responses. Decryption SHALL only happen at send time inside the worker.

#### Scenario: Create message stores encrypted email

- GIVEN a recipient with email "alumno@example.com"
- WHEN a Comunicacion record is created for that recipient
- THEN the `destinatario` field in the database contains the AES-256 encrypted value, not the plaintext email

#### Scenario: Query response does not expose email

- GIVEN a Comunicacion record exists
- WHEN a user queries the message (e.g., tracking or detail endpoint)
- THEN the API response does NOT include the raw email address

#### Scenario: Log output contains no email

- GIVEN a Comunicacion is processed by the worker
- WHEN logs are written during processing
- THEN no plaintext email appears in any log line

#### Scenario: Worker decrypts just before sending

- GIVEN a Comunicacion in Pendiente state with encrypted `destinatario`
- WHEN the worker processes it
- THEN it decrypts the email just before calling SMTP.send()
- AND the decrypted email is not persisted or logged

### R-COM-08 — Migración

The migration SHALL create the `comunicacion` table with all required columns (id, tenant_id, enviado_por, materia_id, destinatario, asunto, cuerpo, estado, lote_id, aprobado_por, fecha_aprobacion, enviado_at, created_at, updated_at). The migration SHALL seed the `comunicacion:enviar` and `comunicacion:aprobar` permissions.

#### Scenario: Migration creates comunicacion table

- GIVEN an empty database
- WHEN migration 0NN is run
- THEN the `comunicacion` table exists with all required columns
- AND the table has `tenant_id` as FK to tenant
- AND the table has proper indices on (tenant_id, lote_id), (tenant_id, estado), and (tenant_id, materia_id)

#### Scenario: Migration seeds permisos

- GIVEN a fresh migration
- WHEN the migration runs
- THEN the `comunicacion:enviar` and `comunicacion:aprobar` permissions are registered in the permisos catalog
