## 1. Modelos de dominio (User, RefreshToken, PasswordResetToken)

- [x] 1.1 Crear `app/models/user.py` con modelo `User`: email (único por tenant), password_hash, totp_secret (cifrado AES-256 nullable), totp_enabled, display_name, is_active — hereda TenantScopedMixin + SoftDeleteMixin
- [x] 1.2 Crear `app/models/auth.py` con modelo `RefreshToken` (user_id FK, token_hash, expires_at, revoked_at nullable) y `PasswordResetToken` (user_id FK, token_hash, expires_at, used_at nullable) — ambos heredan BaseModelMixin
- [x] 1.3 Actualizar `app/models/__init__.py` para re-exportar User, RefreshToken, PasswordResetToken

## 2. Seguridad core — JWT, Argon2id, TOTP

- [x] 2.1 Agregar `pyotp>=1.9,<2.0` a `pyproject.toml` (dependencia para TOTP)
- [x] 2.2 Implementar en `core/security.py`: `hash_password(password) -> str` con Argon2id y `verify_password(password, password_hash) -> bool`
- [x] 2.3 Implementar en `core/security.py`: `create_access_token(data: dict, expires_delta: timedelta | None) -> str` y `decode_access_token(token: str) -> dict` con python-jose, incluyendo jti único y tenant_id en claims
- [x] 2.4 Implementar en `core/security.py`: `generate_totp_secret() -> str` (secreto base32), `get_totp_uri(secret, email) -> str`, `verify_totp(secret, code) -> bool`
- [x] 2.5 Implementar en `core/security.py`: `generate_opaque_token() -> str` (64 bytes hex para refresh/reset tokens) y `hash_token(token: str) -> str` (SHA256)

## 3. Rate limiter

- [x] 3.1 Implementar `core/rate_limiter.py` con `RateLimiter` clase en memoria: `check(ip: str, email: str) -> bool` (True si permite, False si excede 5/60s) y `get_remaining(ip, email) -> int`

## 4. Repository de User

- [x] 4.1 Crear `app/repositories/user_repository.py` con `UserRepository(BaseRepository[User])`: métodos get_by_email, get_by_id con tenant scope, create, update_password, update_totp

## 5. Auth service

- [x] 5.1 Crear `app/services/auth_service.py` con `AuthService`: login (verifica credenciales, rate limiting, decide si requiere 2FA), verify_2fa_login (completa login con TOTP), refresh_token (rota refresh), logout (revoca refresh), forgot_password (genera token), reset_password (valida token + cambia password)

## 6. Router de autenticación

- [x] 6.1 Crear `app/api/v1/routers/auth.py` con endpoint `POST /login` (email + password → access + refresh, o requires_2fa + session_token si 2FA activo)
- [x] 6.2 Agregar endpoint `POST /refresh` (refresh token → nuevo par access + refresh)
- [x] 6.3 Agregar endpoint `POST /logout` (revoca refresh token)
- [x] 6.4 Agregar endpoint `POST /2fa/enroll` (genera secreto TOTP, devuelve URI)
- [x] 6.5 Agregar endpoint `POST /2fa/verify` (verifica TOTP — activa 2FA o completa login)
- [x] 6.6 Agregar endpoint `POST /2fa/disable` (deshabilita 2FA con verificación de password)
- [x] 6.7 Agregar endpoint `POST /forgot` (email → genera token de recuperación)
- [x] 6.8 Agregar endpoint `POST /reset` (token + nueva password → cambia password)
- [x] 6.9 Registrar `auth_router` en `app/main.py` bajo prefijo `/api/auth`

## 7. Dependencies de auth

- [x] 7.1 Implementar `get_current_user` en `core/dependencies.py`: extrae Bearer token, decodifica JWT, resuelve User de DB, verifica is_active
- [x] 7.2 Implementar `get_optional_user` en `core/dependencies.py`: igual que get_current_user pero devuelve None si no hay token (para endpoints públicos que opcionalmente muestran datos contextuales)

## 8. Migración Alembic

- [x] 8.1 Crear `alembic/versions/002_crear_users_tokens.py`: create table users (con unique compuesto tenant_id+email), refresh_tokens, password_reset_tokens
- [x] 8.2 Verificar migración offline — SQL generado correctamente
- [x] 8.3 Verificar downgrade — DROP TABLE correcto

## 9. Tests

- [x] 9.1 (RED) Escribir `tests/test_user_model.py`: estructura User (5 tests: email único por tenant, password_hash, totp_secret nullable, timestamps, soft delete) + RefreshToken (3 tests) + PasswordResetToken (2 tests)
- [x] 9.2 (GREEN) Ajustar modelos hasta que los tests estructurales pasen
- [x] 9.3 (RED) Escribir `tests/test_auth_service.py`: login OK (3 tests: sin 2FA, con 2FA -> requires_2fa, credenciales inválidas -> 401), refresh rotation (2 tests: normal, reuse detection), rate limiting (2 tests)
- [x] 9.4 (GREEN) Implementar auth service hasta que tests pasen
- [x] 9.5 (TRIANGULATE) Escribir `tests/test_auth_api.py` usando async_client: login endpoint E2E (3 tests), 2FA flow completo (3 tests: enroll, verify activate, verify login), recovery flow (3 tests: forgot, reset, token reuse)
- [x] 9.6 (TRIANGULATE) Test regla de oro: enviar parámetros user_id/tenant_id en body no altera identidad
- [x] 9.7 (TRIANGULATE) Test de get_current_user: token válido, expirado, inválido, sin header, usuario inactivo

## 10. Verificación final

- [x] 10.1 Ejecutar suite completa de tests y confirmar verde (132 passed)
- [x] 10.2 Confirmar que ningún archivo .py supera 500 LOC (max: 436 — auth_service.py)
