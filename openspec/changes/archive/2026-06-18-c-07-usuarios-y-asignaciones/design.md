## Context

El modelo `User` actual solo cubre identidad mínima para auth (email, password_hash, display_name, TOTP). No hay datos personales, impositivos ni bancarios. Tampoco existe un modelo de asignación que vincule usuarios con roles y contexto académico. Sin esto no pueden operar los módulos de equipos docentes (C-09), comunicaciones (C-10) ni liquidaciones (C-18).

El módulo de cifrado AES-256-GCM ya existe en `app/core/security.py` (usado para TOTP secret). Los patrones de CRUD con repositorio, tenant-scoping y permisos ya están establecidos en C-01..C-06.

## Goals / Non-Goals

**Goals:**
- Extender User con columnas PII (nombre, apellidos, dni, cuil, cbu, alias_cbu, banco, regional, legajo, legajo_profesional, facturador, estado)
- Cifrar email existente con AES-256-GCM (migración: cifrar emails en la BD)
- Crear modelo Asignacion (usuario × rol × contexto académico × vigencia)
- Endpoints CRUD protegidos para usuarios extendidos y asignaciones
- 5 permisos nuevos registrados en el seed

**Non-Goals:**
- No se cambia el flujo de login (el auth service se adapta para buscar por email cifrado)
- No se implementan aún las vistas "mi equipo" (F4.2) ni asignación masiva (F4.4) — son de C-09
- No se toca el modelo ALUMNO (E6) ni el padrón
- No se implementa clonación de equipos (F4.5) ni modificación de vigencia general (F4.6)

## Decisions

### D-01: Email cifrado + columna `email_hash` para búsqueda determinística

**Decisión**: Agregar columna `email_hash` (SHA-256 del email normalizado) al modelo User. El email se almacena cifrado con AES-256-GCM. La búsqueda por email en login se hace contra `email_hash`, no contra el texto cifrado.

**Por qué**: AES-256-GCM es no-determinístico (usa nonce) — no se puede buscar por email cifrado directamente. Desencriptar toda la tabla en cada login no escala. `email_hash` resuelve la unicidad y búsqueda sin exponer el email en texto plano.

**Alternativa considerada**: Desencriptar en memoria — descartado por performance con N usuarios.

### D-02: PII cifrada en el modelo, no en capa separada

**Decisión**: Los campos PII se almacenan como `String` cifrado en el modelo. El cifrado/descifrado ocurre en los schemas Pydantic (DTOs) en lugar de en el modelo SQLAlchemy. El repositorio guarda/lee texto cifrado; los schemas descifran al leer y cifran al escribir.

**Por qué**: Sigue el patrón existente de separación modelo/schema. El modelo refleja el estado en BD. La transformación ocurre en la capa de presentación.

### D-03: Asignacion con `estado_vigencia` derivado, no almacenado

**Decisión**: `estado_vigencia` es una propiedad calculada: si `hasta IS NULL OR hasta >= today` → Vigente, si `hasta < today` → Vencida. No se almacena en BD.

**Por qué**: Evita sincronización de estados. La fecha `hasta` es la fuente de verdad.

### D-04: Permisos planos `modulo:accion`

**Decisión**: 5 permisos nuevos: `usuarios:list`, `usuarios:create`, `usuarios:update`, `equipos:asignar`, `equipos:revocar`. Se registran en el seed de permisos.

**Por qué**: Sigue el patrón RBAC existente (`estructura:gestionar`, `calificaciones:importar`, etc.).

### D-05: CRUD de usuarios como admin router plano

**Decisión**: Los endpoints de usuarios van en `backend/app/api/v1/routers/admin/usuarios.py` (no un subrouter anidado). Asignaciones va en `backend/app/api/v1/routers/asignaciones.py` (ruta `/api/asignaciones`).

**Por qué**: Consistencia con el patrón existente de routers admin planos. `/api/asignaciones` sin `/admin` porque COORDINADOR también accede.

### D-06: Soft delete en Asignacion vía fin de vigencia

**Decisión**: No hay DELETE físico. Se asigna `hasta = today` para revocar. El endpoint `DELETE` establece `hasta = today` y cambia lógicamente el estado a vencida.

**Por qué**: Consistencia con regla de negocio RN (asignaciones vencidas se conservan en histórico). Soft delete tradicional ocultaría la asignación — aquí queremos que sea visible pero inactiva.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| **Email hash expone correlación**: aunque el email está cifrado, el hash SHA-256 permite correlacionar同一 emails entre tenants si el mismo email se registra en dos lugares | Usar SHA-256(tenant_id + email_normalizado) en lugar de solo email. Añadir pepper (la ENCRYPTION_KEY). |
| **PII en logs**: un error handler podría loguear el body del request con datos sensibles | Sanitizar schemas de usuario con `repr=False` en campos sensibles; verificar que no haya logging automático de request bodies |
| **Performance en listados**: desencriptar N emails en GET /usuarios es O(N) | El listado devuelve solo datos no cifrados (nombre, legajo, estado) + último 4 chars del email. Los datos PII completos solo se exponen en GET /usuarios/{id}. |
| **Seed de permisos**: los permisos nuevos deben existir antes de usarlos | Agregarlos al seed existente de permisos y roles. Si el seed no se ejecuta, los endpoints fallan con 403. |
| **Migración de emails existentes**: usuarios creados antes tienen email en texto plano | La migración 006 lee cada email, lo cifra con AES-256-GCM, y escribe el hash + ciphertext en la misma transacción. |
