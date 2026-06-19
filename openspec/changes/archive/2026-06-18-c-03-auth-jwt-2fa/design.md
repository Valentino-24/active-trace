## Context

Activia-trace necesita autenticación antes de que cualquier endpoint de negocio pueda operar. C-02 dejó los cimientos: modelo `Tenant`, mixins base, repositorio genérico con scope de tenant, cifrado AES-256 y la infraestructura de base de datos. No existe modelo `User` ni lógica de sesión.

Este change implementa el sistema completo de autenticación: login con credenciales, sesión JWT con refresh rotation, 2FA TOTP opcional y recuperación de contraseña. Es **CRITICAL** (governance nivel CRÍTICO) porque toca el modelo de identidad y sesión.

## Goals / Non-Goals

**Goals:**
- Modelo `User` con email único por tenant, password hash Argon2id, TOTP secret nullable.
- Login (`POST /api/auth/login`) con rate limiting 5/60s por IP+email.
- Sesión JWT con access token 15 min + refresh token con rotación (reuso invalida el anterior).
- Logout (`POST /api/auth/logout`) que revoca la sesión activa.
- 2FA TOTP opcional por usuario: enrolar (`POST /api/auth/2fa/enroll`) y verificar (`POST /api/auth/2fa/verify`) como gate entre credenciales y emisión de sesión.
- Recuperación de contraseña: `POST /api/auth/forgot` (token único por email, expiración 30 min) + `POST /api/auth/reset`.
- Dependency `get_current_user` que resuelve identidad + tenant desde el JWT.
- Tests de todos los flujos, incluyendo regla de oro (identidad inalterable por parámetros de request).

**Non-Goals:**
- RBAC / permisos finos (`require_permission`) → C-04.
- Impersonation → C-05 (audit log) o posterior.
- Envío real de emails (solo logging del token) → se integra con el worker de comunicaciones en change futuro (C-12). Por ahora el forgot token se loggea y se devuelve en la respuesta para testing.
- Frontend de login → C-21 (frontend shell).
- SSO con Moodle → Fase 2 (ADR-001).

## Decisions

### D1 — Modelo `User` con email único por tenant

El modelo `User` hereda de `TenantScopedMixin` y lleva:
- `email`: String(255), único **dentro del tenant** (unique constraint compuesto `(tenant_id, email)`).
- `password_hash`: String(255), hash Argon2id.
- `totp_secret`: String(64), nullable — secreto TOTP cifrado con AES-256 (reusa `core/security.py`).
- `totp_enabled`: Boolean, default False.
- `display_name`: String(255), nombre visible.
- `is_active`: Boolean, default True.

Se crean además:
- `RefreshToken`: asociado a User con `token_hash` (SHA256 del token real), `expires_at`, `revoked_at` nullable.
- `PasswordResetToken`: asociado a User con `token_hash`, `expires_at`, `used_at` nullable.

**Alternativa descartada**: meter refresh tokens como JSON en el user. Se descarta porque no permite consultas eficientes de revocación ni auditoría de sesiones.

### D2 — JWT con python-jose (ya en pyproject.toml)

Se usa `python-jose[cryptography]` que ya está declarado como dependencia. Claims del access token:
- `sub`: user UUID
- `tenant_id`: tenant UUID
- `roles`: lista de strings (vacíos por ahora, se llenan en C-04)
- `exp`, `iat`, `jti` (unique ID para el token)

El refresh token NO es JWT — es un token opaco (64 bytes aleatorios en hex) almacenado como SHA256 en la tabla `refresh_tokens`. Esto permite revocación y detección de reuso.

**Alternativa descartada**: refresh token como JWT largo. Se descarta porque un JWT no se puede revocar sin una blacklist, complicando la detección de reuso.

### D3 — Rate limiter en memoria

Implementación simple: diccionario `{ip:email: deque }` con timestamps de intentos. Se limpia en cada verificación (descarta entradas > 60s). Suficiente para MVP. Cuando haya múltiples instancias, se migrará a Redis.

### D4 — 2FA como gate en el login flow

El flujo de login con 2FA es:
1. `POST /auth/login` con email + password → si credenciales OK y user tiene 2FA habilitado → responde `200` con `{"requires_2fa": true, "session_token": "<token>"}` (token temporal firmado, 5 min).
2. `POST /auth/2fa/verify` con `session_token` + `totp_code` → si OK → emite access + refresh token.

Sin 2FA: login devuelve access + refresh directamente.

### D5 — `get_current_user` como dependency

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    user = await user_repository.get_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401)
    return user
```

`oauth2_scheme` es `HTTPBearer` de FastAPI (header `Authorization: Bearer <token>`).

Se registra en `app.state.current_user` para acceso en otros puntos si es necesario, pero la dependency es el mecanismo oficial.

### D6 — Sin envío de email real

El endpoint `POST /api/auth/forgot` genera el token, lo persiste, loggea el enlace de recuperación y lo devuelve en la respuesta. Esto permite testear y debuggear sin depender de infraestructura de email. Cuando se implemente el worker de comunicaciones (C-12), se reemplazará el log + return por un envío real.

## Risks / Trade-offs

- **[Rate limiter en memoria no escala a multi-instancia]** → Mitigación: aceptado para MVP. Cuando haya más de una instancia de API, migrar a Redis.
- **[Forgot token devuelto en response es inseguro para producción]** → Mitigación: aceptado para MVP. El contrato del endpoint ya contempla que el token se devuelve; en producción se envía por email y se quita del response.
- **[2FA TOTP sin recovery codes]** → Trade-off: se implementa solo el flujo básico de TOTP. Códigos de recuperación (backup codes) se agregan en un change futuro si es necesario. Mientras tanto, un ADMIN puede deshabilitar 2FA para un usuario.
- **[python-jose puede tener vulnerabilidades conocidas]** → Mitigación: se fija versión >=3.3.0 y se mantiene actualizado con dependabot. Alternativa futura: migrar a PyJWT con cryptography.

