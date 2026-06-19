## Why

El modelo `User` actual solo cubre identidad mínima para auth (email, password_hash, display_name). No hay forma de gestionar datos completos del docente (datos personales, impositivos, bancarios) ni de modelar su vinculación con roles y contexto académico (qué materia, carrera, cohorte, comisiones atiende y por qué período). Sin esto no pueden operar los módulos de equipos docentes (C-09), comunicaciones (C-10) ni liquidaciones (C-18). Implementar Usuario extendido con PII cifrada y Asignación con vigencia es requisito fundacional para todo el flujo de gestión académica.

## What Changes

- **Extender modelo User** con columnas PII: `nombre`, `apellidos`, `dni` (cifrado), `cuil` (cifrado), `cbu` (cifrado), `alias_cbu` (cifrado), `banco`, `regional`, `legajo`, `legajo_profesional`, `facturador`, `estado` (Activo/Inactivo).
- **Cifrar `email`** existente con AES-256-GCM (hoy está en texto plano). Migración: cifrar emails existentes.
- **Crear modelo Asignacion**: vincula `Usuario` ↔ `Rol` ↔ contexto académico (`Materia`, `Carrera`, `Cohorte`, comisiones) con vigencia (`desde`, `hasta`).
- **Endpoint `GET /api/admin/usuarios`**: listar usuarios del tenant con filtros.
- **Endpoint `POST /api/admin/usuarios`**: crear usuario con PII cifrada.
- **Endpoint `GET /api/admin/usuarios/{id}`**: obtener detalle (PII desencriptada solo para ADMIN).
- **Endpoint `PATCH /api/admin/usuarios/{id}`**: actualizar datos (PII se recibe en texto plano, se cifra al guardar).
- **Endpoint `POST /api/asignaciones`**: crear asignación (ADMIN, COORDINADOR con permiso `equipos:asignar`).
- **Endpoint `DELETE /api/asignaciones/{id}`**: revocar asignación (baja lógica por fin de vigencia).
- **Endpoint `GET /api/asignaciones`**: listar asignaciones con filtros por materia, carrera, cohorte, usuario, rol, vigencia.
- **Permisos nuevos**: `usuarios:list`, `usuarios:create`, `usuarios:update`, `equipos:asignar`, `equipos:revocar`.
- **Migración Alembic 006**: schema de nuevas columnas + tabla `asignaciones` + cifrar emails existentes.
- **Tests**: ≥80% cobertura en nuevos endpoints, ≥90% reglas de negocio (unicidad email, PII cifrada en reposo, asignación vencida no otorga permisos).

## Capabilities

### New Capabilities
- `usuarios`: gestión de usuarios extendidos con PII (alta, consulta, edición, activación/desactivación). Excluye auth (eso es `user-auth` existente).
- `asignaciones`: gestión de asignaciones usuario ↔ rol ↔ contexto académico con vigencia.

### Modified Capabilities
- `user-auth`: los campos `email` ahora se almacenan cifrados — afecta el login y la verificación de unicidad. El requerimiento "email único por tenant" se mantiene, pero la comparación debe hacerse desencriptando o contra hash determinístico del email.

## Impact

- **Modelos**: `User` se extiende (~12 columnas nuevas). Se crea `Asignacion`.
- **API**: 6 nuevos endpoints protegidos por RBAC.
- **Migración**: `006_extender_usuario_crear_asignacion.py` — añade columnas, crea tabla, migra emails existentes a cifrado.
- **Auth service**: `authenticate_user` debe poder buscar por email cifrado (desencriptar o buscar por hash determinístico).
- **Encryption**: el módulo `app/core/security.py` ya tiene `encrypt()`/`decrypt()` AES-256-GCM — aplicar a PII en los repositorios.
- **Reglas duras afectadas**: #8 (identidad desde sesión — los endpoints de admin verifican JWT + permiso), #9 (multi-tenancy row-level — `tenant_id` en Asignacion), #10 (RBAC fino — permisos nuevos), #12 (PII cifrada), #14 (UUID interno).
