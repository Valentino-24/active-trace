## Why

Activia-trace es multi-tenant y maneja datos académicos sensibles de alumnos, docentes y financieros. Sin autenticación no hay trazabilidad, y sin trazabilidad el producto no cumple su propósito. Este change implementa el sistema de login, sesión JWT con refresh rotation, 2FA TOTP opcional y recuperación de contraseña — el punto de entrada único al sistema para todos los roles.

C-02 dejó el cimiento (Tenant, mixins, repositorio base). Sin C-03 ningún endpoint puede identificar quién hace la request, y por lo tanto ningún endpoint de negocio puede operar. Es el gate que desbloquea todo el árbol de dependencias.

## What Changes

- **Nuevo modelo `User`** con email único por tenant, password hash (Argon2id), 2FA TOTP secret (nullable), y atributos de sesión/recuperación.
- **Nuevo modelo `RefreshToken`** como tabla de sesiones con rotación (token reuse invalida la sesión).
- **Nuevo modelo `PasswordResetToken`** para recuperación (token de un solo uso con expiración corta).
- **`core/security.py`** — se completa con: hash/verify Argon2id, JWT sign/verify (access + refresh), TOTP generate/verify.
- **`core/dependencies.py`** — se agrega `get_current_user` que extrae y valida el JWT del header `Authorization`, resuelve usuario + tenant.
- **`api/v1/routers/auth.py`** — endpoint `POST /api/auth/login` con rate limiting por IP+email (5/60s).
- **`api/v1/routers/auth.py`** — endpoint `POST /api/auth/refresh` con rotación de refresh token.
- **`api/v1/routers/auth.py`** — endpoint `POST /api/auth/logout` que revoca la sesión actual.
- **`api/v1/routers/auth.py`** — endpoints 2FA: `POST /api/auth/2fa/enroll` (genera secreto, devuelve URI), `POST /api/auth/2fa/verify` (valida TOTP y completa el login).
- **`api/v1/routers/auth.py`** — endpoints de recuperación: `POST /api/auth/forgot` (envía token por email), `POST /api/auth/reset` (cambia password con token válido).
- **Nuevo modelo `PasswordResetToken`** para recuperación.
- **Rate limiter** en memoria (por IP+email) para login endpoint.
- **Migración Alembic 002**: tabla `users`, `refresh_tokens`, `password_reset_tokens`.
- Tests completos de todos los flujos.

## Capabilities

### New Capabilities
- `user-auth`: Autenticación de usuarios con email + password (Argon2id), emisión de JWT access token (15 min) + refresh token con rotación, cierre de sesión.
- `user-2fa`: Second factor TOTP opcional — enrolamiento, verificación y gate entre login y emisión de sesión.
- `password-recovery`: Recuperación de contraseña por email con token de un solo uso y expiración corta.
- `auth-dependencies`: Dependency `get_current_user` para FastAPI que resuelve identidad + tenant desde el JWT verificado.

### Modified Capabilities
- *(ninguna — primer change de auth)*

## Impact

- **Nuevos modelos**: `User` (con email, password_hash, totp_secret nullable), `RefreshToken` (user_id, token_hash, expires_at, revoked_at nullable), `PasswordResetToken` (user_id, token_hash, expires_at, used_at nullable). Todos heredan de `TenantScopedMixin` (tenant_id) y `SoftDeleteMixin`.
- **core/security.py**: se expande con JWT utils (create_access_token, decode_token), Argon2id (hash_password, verify_password), TOTP (generate_totp_secret, verify_totp).
- **core/dependencies.py**: se agrega `get_current_user` como dependency que parsea `Authorization: Bearer <token>`, verifica el JWT, resuelve el User de DB y lo inyecta.
- **Nuevo router**: `api/v1/routers/auth.py` con 6 endpoints.
- **Nuevo service**: `services/auth_service.py` con lógica de login, refresh, 2FA, recovery.
- **Nuevo repository**: `repositories/user_repository.py` (aunque sea simple, respeta la arquitectura).
- **Rate limiter**: implementación simple en memoria (diccionario con deque/time-based), suficiente para MVP.
- **Dependencias**: se usa `python-jose` (ya declarado en pyproject.toml) para JWT, `argon2-cffi` (ya declarado) para password hashing, y `pyotp` (nueva dependencia) para TOTP 2FA.
- **Migración Alembic**: `002_crear_users_tokens.py`.
- **Tests**: cobertura completa de login exitoso/fallido, refresh rotation (reuso invalida), 2FA flow, rate limiting, recovery, y regla de oro (identidad no alterable por parámetros).
