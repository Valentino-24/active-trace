# Arquitectura — activia-trace

**Producto**: activia-trace
**Versión del documento**: 0.1 (draft inicial)
**Fecha**: 2026-05-28
**Estado**: Draft — arquitectura objetivo (target), aún sin implementación
**Referencias**: [PRD](./PRD.md) · [KB — arquitectura observada de PulseUPs](../knowledge-base/08_arquitectura_propuesta.md) · [Modelo de datos](../knowledge-base/04_modelo_de_datos.md)

> ⚠️ **Diferencia clave con `knowledge-base/08`**: ese archivo documenta la arquitectura **observada de PulseUPs** (PHP MPA monolítico — el sistema que reemplazamos). **Este** documento define la arquitectura **objetivo de activia-trace**, que NO comparte nada con el stack viejo salvo el dominio.

---

## 1. Propósito y filosofía

activia-trace adopta **el mismo stack y los mismos patrones que [active-ia](https://github.com/) (correción automática)** — un sistema hermano ya en producción, probado, con Clean Architecture. No reinventamos: clonamos lo que funciona y le sumamos lo que activia-trace necesita de más (multi-tenancy real, modelo de roles rico, auth a prueba de balas, integración Moodle por Web Services).

**Principios rectores:**

1. **CONCEPTOS > CÓDIGO** — la arquitectura se diseña antes de tipear. Este doc es el contrato.
2. **Separación estricta de capas** — la lógica de negocio nunca toca HTTP ni SQL directamente.
3. **La identidad jamás se deriva de un parámetro de request** — la lección #1 que aprendimos destripando PulseUPs ([P11](./PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).
4. **Multi-tenant desde el día 0** — no es un retrofit; es la raíz del modelo.
5. **Todo audita** — el nombre del producto es *trace*. Cada acción significativa queda atribuida.

---

## 2. Stack tecnológico

Clonado de active-ia salvo los **deltas** marcados (lo que activia-trace agrega).

### Backend

| Componente | Tecnología | Notas |
|------------|-----------|-------|
| Lenguaje | **Python 3.13** | Igual que active-ia |
| Framework | **FastAPI** | API REST async |
| ORM | **SQLAlchemy 2.0** (async) | Mapeo + queries en repositories |
| Migraciones | **Alembic** | Una migración por cambio de schema |
| Base de datos | **PostgreSQL** | JSONB para criterios/scores configurables |
| Validación | **Pydantic v2** | DTOs request/response (schemas) |
| Auth | **JWT** (access corto + refresh rotation) + **Argon2id** para hashing de passwords | 🔶 *delta*: active-ia usa JWT simple; acá endurecemos (ver §5) |
| Cifrado en reposo | **AES-256** | Para PII sensible (CBU, DNI) y secretos |
| Background jobs | **Worker async** (cola de mails) | 🔶 *delta vs active-ia*: PulseUPs tenía worker Pend→Send→OK/Fail; lo replicamos |
| Integraciones | **N8N** + **Moodle Web Services** | 🔶 *delta*: Moodle WS (`core_grades_get_grades`, etc.) es nuevo |
| Testing | **pytest** + coverage | ≥80% líneas, ≥90% reglas de negocio ([RNF-15](./PRD.md#mantenibilidad)) |

### Frontend

| Componente | Tecnología | Notas |
|------------|-----------|-------|
| Framework | **React 18** + **TypeScript** | Sin `any`, sin class components |
| Bundler | **Vite** | HMR en dev |
| Server state | **React Query (TanStack Query)** | Todo fetch pasa por hooks de `services/` |
| Forms | **React Hook Form + Zod** | Validación tipada |
| Estilos | **Tailwind CSS** | Sin CSS modules, sin inline (salvo valores dinámicos) |
| HTTP | **Axios** | Cliente centralizado en `@/shared/services/api` |
| Estructura | **Feature-based modules** | `features/{name}/{components,hooks,services,types,pages}` |

### Infraestructura

| Componente | Tecnología |
|------------|-----------|
| Contenedores | **Docker** + docker-compose (local y prod) |
| Deploy | **Easypanel** (igual que active-ia) |
| Observabilidad | Logs estructurados JSON + **OpenTelemetry** ([RNF-17](./PRD.md#mantenibilidad)) |
| CI/CD | build + test + lint + deploy automatizado ([RNF-16](./PRD.md#mantenibilidad)) |

---

## 3. Arquitectura backend — Clean Architecture

Idéntico patrón a active-ia. El flujo de una request es **unidireccional** y cada capa tiene una sola responsabilidad:

```
REQUEST
   │
   ▼
┌──────────────┐  HTTP, validación Pydantic, auth/authz. NADA de lógica de negocio.
│   Routers    │
└──────┬───────┘
       ▼
┌──────────────┐  Lógica de negocio. NO accede a la DB directamente.
│   Services   │
└──────┬───────┘
       ▼
┌──────────────┐  TODAS las queries SQLAlchemy. NADA de reglas de negocio.
│ Repositories │
└──────┬───────┘
       ▼
┌──────────────┐  Entidades ORM (SQLAlchemy).
│    Models    │
└──────┬───────┘
       ▼
   PostgreSQL
```

**Reglas no negociables** (heredadas de active-ia, ampliadas):

- **Nunca** lógica de negocio en Routers.
- **Nunca** acceso directo a DB desde Services (siempre vía Repository).
- Secretos (API keys, tokens externos) **siempre** AES-256 — jamás en texto plano.
- **Soft delete** siempre (audit). Nunca hard delete.
- Validar permisos por rol **en cada endpoint** — y además scope por tenant (ver §6).
- Máximo **500 LOC por archivo** backend.
- Manejo de errores estandarizado:

  | Tipo | Respuesta |
  |------|-----------|
  | Validación | `HTTPException 400` |
  | No autenticado | `HTTPException 401` |
  | Sin permiso (authz) | `HTTPException 403` |
  | No encontrado | `HTTPException 404` |
  | Error IA / N8N / Moodle | `HTTPException 502` + retry |
  | Interno | `HTTPException 500` + log detallado |

---

## 4. Estructura de directorios

### Backend (`backend/`)

```
backend/
├── app/
│   ├── main.py                  # Bootstrap FastAPI
│   ├── api/v1/routers/          # Routers por dominio
│   ├── core/
│   │   ├── config.py            # Settings (env vars)
│   │   ├── security.py          # JWT, Argon2, AES-256
│   │   ├── permissions.py       # RBAC: matriz rol × permiso
│   │   ├── tenancy.py           # 🔶 NUEVO: resolución y aislamiento de tenant
│   │   ├── dependencies.py      # DI: get_current_user, get_tenant, require_permission
│   │   └── exceptions.py
│   ├── models/                  # SQLAlchemy ORM
│   ├── schemas/                 # Pydantic DTOs
│   ├── repositories/            # Queries (tenant-scoped por defecto)
│   ├── services/                # Lógica de negocio
│   ├── integrations/
│   │   ├── n8n_client.py
│   │   └── moodle_ws.py         # 🔶 NUEVO: cliente Moodle Web Services
│   └── workers/                 # 🔶 NUEVO: worker de cola de mails
├── alembic/                     # Migraciones
└── tests/
```

### Frontend (`frontend/`)

```
frontend/src/
├── features/
│   └── {dominio}/               # auth, alumnos, materias, comisiones,
│       ├── components/          #   atrasados, comunicacion, equipos,
│       ├── hooks/               #   encuentros, coloquios, liquidaciones,
│       ├── services/            #   auditoria, perfil
│       ├── types/
│       └── pages/
└── shared/
    ├── services/api.ts          # Axios centralizado + interceptor JWT/refresh
    ├── components/              # UI reutilizable
    └── hooks/
```

---

## 5. Modelo de seguridad — el corazón de activia-trace

> Esta sección existe porque **el pecado original de PulseUPs era de seguridad** ([P11](./PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)). Si fallamos acá, fallamos en todo.

### 5.1 Autenticación

- Login con **email + password** ([RF-01](./PRD.md#auth-roles-y-tenants)). Password hasheado con **Argon2id** (nunca MD5/SHA simple, nunca texto plano).
- **2FA opcional (TOTP)** por usuario.
- Recuperación de contraseña por email con token de un solo uso y expiración corta ([RF-02](./PRD.md#auth-roles-y-tenants)).
- Sesión = **JWT firmado**, access token de vida corta (**15 min**, [RNF-09](./PRD.md#seguridad)) + **refresh token con rotación** (un refresh usado se invalida).
- El JWT lleva claims mínimos: `sub` (user id), `tenant_id`, `roles`, `exp`. **Nada de permisos en el token** — se resuelven server-side.

### 5.2 Autorización (RBAC)

- Roles ricos ([RF-04](./PRD.md#auth-roles-y-tenants)): **ALUMNO, TUTOR, PROFESOR, COORDINADOR, ADMIN, FINANZAS**. (Reemplaza el flag binario `is_admin` opaco de PulseUPs, [P10](./PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).
- **Permisos finos por feature**, no por rol monolítico. Matriz rol × permiso en `core/permissions.py`.
- Cada endpoint declara el permiso requerido vía dependency (`require_permission("entregas:write")`). Sin él → `403`.

### 5.3 Cómo activia-trace MATA la vuln `?leg=X` (P11)

| Vector en PulseUPs | Defensa en activia-trace |
|--------------------|--------------------------|
| La identidad salía de un **parámetro de URL** (`?leg=1`) | La identidad **solo** sale del JWT firmado y verificado. Ningún parámetro de request puede alterar quién sos. |
| Cambio de identidad **sin re-autenticar** | Cambiar de identidad es imposible sin un nuevo login (o sin la feature de impersonation permisada — ver abajo). |
| Privilegio derivado de `is_admin` binario | RBAC con permisos finos resueltos server-side en cada request. |
| Impersonation **silenciosa, no auditada** | La impersonation legítima (soporte/admin) es una **feature explícita**: requiere permiso `impersonation:use`, genera un **token de impersonation distinguible**, y **registra en el audit log** quién impersona a quién, desde cuándo y hasta cuándo ([RF-05](./PRD.md#auth-roles-y-tenants), [RNF-12](./PRD.md#seguridad)). Toda acción bajo impersonation queda atribuida al actor real, no a la víctima. |

> **Regla de oro grabada en piedra**: *la identidad y el tenant del request se derivan EXCLUSIVAMENTE del JWT verificado. Cualquier `id`, `legajo` o `tenant` que venga en query string, body o header se trata como dato de entrada a validar contra los permisos del usuario actual — NUNCA como su identidad.*

### 5.4 Otras defensas transversales

- **HTTPS/TLS 1.3** en todo el tráfico ([RNF-07](./PRD.md#seguridad)).
- **PII cifrada en reposo** (CBU, DNI) con AES-256 ([RNF-08](./PRD.md#seguridad)).
- **CSRF protection** en endpoints state-changing ([RNF-10](./PRD.md#seguridad)).
- **Rate limiting** por IP y por usuario ([RNF-11](./PRD.md#seguridad)).
- **Audit log append-only** (idealmente write-once), sin límite de retención ([RNF-12](./PRD.md#seguridad), [RF-38](./PRD.md#auditoría)) — corrige el cap de 200 de PulseUPs.

---

## 6. Multi-tenancy

🔶 **Esto NO existe en active-ia ni en PulseUPs** — es nativo de activia-trace ([RF-03](./PRD.md#auth-roles-y-tenants), [RNF-22](./PRD.md#multi-tenancy)).

- **Tenant** es el primer nivel del modelo (una institución = un tenant; TUPAD es el primero).
- **Estrategia (a decidir en ADR-002, ver §10)**: row-level security como mínimo (columna `tenant_id` en toda tabla + filtro automático en cada repository), database-per-tenant si el negocio lo justifica.
- El `tenant_id` se resuelve del JWT (§5.1) y se inyecta vía dependency. **Los repositories filtran por tenant por defecto** — un query sin scope de tenant es un bug que debe fallar en code review.
- **Los datos jamás cruzan tenants.** Test obligatorio: un usuario del tenant A nunca puede leer/escribir datos del tenant B.
- Configuración por tenant ([RNF-23](./PRD.md#multi-tenancy)): idioma, branding, plantillas de mail, catálogo de escalas textuales, flag de aprobación de mails.

---

## 7. Integraciones

### 7.1 Moodle (Web Services) — 🔶 nuevo

- Sync vía Moodle WS: `core_grades_get_grades`, `core_user_get_users_by_field`, etc. ([RF-06](./PRD.md#ingesta-y-datos)).
- **Sync nocturna automática** + sync on-demand.
- **Fallback**: import manual `.xlsx`/`.csv` para tenants sin acceso WS ([RF-07](./PRD.md#ingesta-y-datos)) — preserva el flujo conocido de PulseUPs.
- Cliente aislado en `integrations/moodle_ws.py`; los errores mapean a `502 + retry`.

### 7.2 Cola de mails (worker async) — 🔶 nuevo

- Replica el modelo probado de PulseUPs: estados **Pend → Send → OK/Fail** y **Pend → Canc** ([RF-18](./PRD.md#comunicación)).
- **Preview obligatorio** antes de encolar ([RF-17](./PRD.md#comunicación)).
- **Aprobación humana opcional por tenant** ([RF-19](./PRD.md#comunicación)).
- Plantillas con variables `{{alumno.nombre}}`, `{{materia.nombre}}` ([RF-20](./PRD.md#comunicación)).

### 7.3 N8N

- Igual que active-ia: orquestación de flujos. Se evalúa si activia-trace lo necesita en MVP o si el worker propio alcanza.

---

## 8. Persistencia y modelo de datos

- PostgreSQL. Modelo detallado heredado/evolucionado de [`knowledge-base/04`](../knowledge-base/04_modelo_de_datos.md).
- **JSONB** para estructuras configurables (criterios, escalas, scores).
- Cambios estructurales clave vs PulseUPs (ver [PRD §9](./PRD.md)):
  - `Tenant` como raíz.
  - **Padrón con historial** (versionado, no upsert destructivo — corrige [P2](./PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).
  - **Catálogo único de materias** por tenant (corrige [P1](./PRD.md#12-problemas-observados-en-pulseups-que-activia-trace-debe-resolver)).
  - Audit log append-only sin cap.
- **Identidad de docente**: PulseUPs usaba `legajo` como natural key visible en URLs ([RN-25](../knowledge-base/05_reglas_de_negocio.md#rn-25)) — parte de la causa de P11. activia-trace usa **id interno (UUID) para identidad/auth** y conserva `legajo` solo como **atributo de negocio**, nunca como credencial ni como selector de identidad.

---

## 9. Convenciones

### Commits (Conventional Commits)

`<type>(<scope>): <descripción>`

- **Types**: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- **Scopes**: `auth`, `tenancy`, `users`, `alumnos`, `materias`, `comisiones`, `entregas`, `comunicacion`, `equipos`, `encuentros`, `coloquios`, `liquidaciones`, `auditoria`, `moodle`, `api`, `ui`
- **Sin** atribución AI / `Co-Authored-By`.

### Código

- Backend: Clean Architecture estricta (§3), ≤500 LOC/archivo.
- Frontend: componentes funcionales TS, <200 LOC, pages lazy-loaded, loading + error states siempre.

### Variables de entorno clave

| Variable | Propósito |
|----------|-----------|
| `DATABASE_URL` | Conexión PostgreSQL |
| `SECRET_KEY` | Firma JWT (mín. 32 chars) |
| `ENCRYPTION_KEY` | AES-256 para PII/secretos (exactamente 32 chars) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración access token (default 15) |
| `MOODLE_WS_TOKEN` / `MOODLE_WS_URL` | Acceso a Moodle Web Services (por tenant) |
| `N8N_WEBHOOK_URL` | Servicio N8N |

---

## 10. Decisiones de arquitectura pendientes (ADRs a redactar)

| ADR | Decisión | Estado |
|-----|----------|--------|
| ADR-001 | ¿Auth propio (email+pass) vs federado con Moodle SSO? | Abierto — ligado a [OQ-04](./PRD.md#12-open-questions-a-resolver-antes-de-cerrar-el-prd) |
| ADR-002 | Multi-tenancy: row-level (`tenant_id`) vs database-per-tenant | Abierto — ligado a [OQ-06](./PRD.md#12-open-questions-a-resolver-antes-de-cerrar-el-prd) |
| ADR-003 | Worker propio (asyncio/Celery/ARQ) vs N8N para la cola de mails | Abierto |
| ADR-004 | ¿Verificar si `?leg=X` de PulseUPs es pre-auth (full bypass) o solo escalada post-login? | Abierto — ligado a [PA-21](../knowledge-base/10_preguntas_abiertas.md#pa-21) / P11 |

---

## 11. Resumen — deltas vs active-ia

Lo que activia-trace **construye de más** sobre la base de active-ia:

1. **Multi-tenancy nativo** (§6).
2. **Modelo de roles rico + RBAC fino** (§5.2) en vez de `is_admin` binario.
3. **Auth endurecida**: Argon2id, 2FA, access 15 min + refresh rotation, impersonation auditada (§5).
4. **Integración Moodle por Web Services** + fallback manual (§7.1).
5. **Worker de cola de mails** con preview y aprobación (§7.2).
6. **Audit log append-only sin límite** (§5.4).
7. **Padrón versionado** y **catálogo único de materias** (§8).

Todo lo demás —Clean Architecture, FastAPI, SQLAlchemy, React/Vite/Tailwind/React Query, Docker/Easypanel— es **clonado tal cual de active-ia**.
