"""Security utilities: AES-256-GCM, Argon2id, JWT, TOTP, opaque tokens.

Provides encryption at rest (AES-256-GCM), password hashing (Argon2id),
JWT access tokens, TOTP 2FA, and opaque token generation for refresh/reset.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from jose import JWTError, jwt

# ── Constants ────────────────────────────────────────────────────────────────

NONCE_LENGTH = 12  # 96-bit nonce recommended for GCM
TAG_LENGTH = 16  # 128-bit authentication tag
KEY_LENGTH = 32  # 256-bit AES key

_hasher = PasswordHasher()


def _get_settings():
    """Lazy-load Settings to avoid import-time validation errors in tests."""
    from app.core.config import Settings

    return Settings()  # type: ignore[call-arg]


# ── AES-256-GCM encryption (PII at rest) ─────────────────────────────────────


def _validate_key(key: bytes) -> None:
    """Ensure the encryption key is exactly 32 bytes."""
    if len(key) != KEY_LENGTH:
        raise ValueError(
            f"Encryption key must be exactly {KEY_LENGTH} bytes "
            f"(got {len(key)})"
        )


def encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt plaintext with AES-256-GCM.

    Args:
        plaintext: UTF-8 string to encrypt.
        key: 32-byte AES-256 key.

    Returns:
        Base64-encoded string containing nonce + ciphertext + tag.

    Raises:
        ValueError: If key length is not 32 bytes.
    """
    _validate_key(key)
    nonce = os.urandom(NONCE_LENGTH)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ciphertext = cipher.update(plaintext.encode("utf-8")) + cipher.finalize()
    payload = nonce + ciphertext + cipher.tag
    return base64.b64encode(payload).decode("ascii")


def decrypt(ciphertext_b64: str, key: bytes) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext.

    Args:
        ciphertext_b64: Output from encrypt().
        key: 32-byte AES-256 key (MUST be the same key used to encrypt).

    Returns:
        Original plaintext string.

    Raises:
        ValueError: If key length is invalid.
        cryptography.exceptions.InvalidTag: If the ciphertext was tampered
            with or the key is wrong.
    """
    _validate_key(key)
    payload = base64.b64decode(ciphertext_b64)
    if len(payload) < NONCE_LENGTH + TAG_LENGTH:
        raise ValueError("Ciphertext payload is too short")
    nonce = payload[:NONCE_LENGTH]
    tag = payload[-TAG_LENGTH:]
    ciphertext = payload[NONCE_LENGTH:-TAG_LENGTH]
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).decryptor()
    plaintext_bytes = cipher.update(ciphertext) + cipher.finalize_with_tag(tag)
    return plaintext_bytes.decode("utf-8")


# ── Argon2id password hashing ────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: Plain-text password.

    Returns:
        Argon2id hash string.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its Argon2id hash.

    Args:
        password: Plain-text password to verify.
        password_hash: Argon2id hash string.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


# ── JWT access tokens ────────────────────────────────────────────────────────


def _get_jwt_secret() -> str:
    """Get the JWT signing secret from settings."""
    return _get_settings().secret_key


def _get_access_token_expire_minutes() -> int:
    """Get the access token expire minutes from settings."""
    return _get_settings().access_token_expire_minutes


def create_impersonation_token(
    user_id: uuid.UUID,
    impersonator_id: uuid.UUID,
    tenant_id: uuid.UUID,
    expires_delta: timedelta | None = None,
    _secret_key: str | None = None,
) -> str:
    """Create a JWT for an impersonated session.

    The token contains both `sub` (impersonated user) and
    `impersonator_id` (real actor) so that get_current_user can
    distinguish impersonated sessions from normal ones.

    Args:
        user_id: UUID of the user being impersonated (sub claim).
        impersonator_id: UUID of the user performing the impersonation.
        tenant_id: Tenant scope of the impersonated user.
        expires_delta: Token lifetime (default: from Settings, 15 min).
        _secret_key: Override secret key (for testing only).

    Returns:
        Encoded JWT string.
    """
    return create_access_token(
        data={
            "sub": str(user_id),
            "impersonator_id": str(impersonator_id),
            "tenant_id": str(tenant_id),
            "purpose": "impersonation",
        },
        expires_delta=expires_delta,
        _secret_key=_secret_key,
    )


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
    _secret_key: str | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to include (sub, tenant_id, roles, etc.).
        expires_delta: Token lifetime (default: from Settings, 15 min).
        _secret_key: Override secret key (for testing only).

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=_get_access_token_expire_minutes()))
    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
        }
    )
    key = _secret_key or _get_jwt_secret()
    return jwt.encode(to_encode, key, algorithm="HS256")


def decode_access_token(
    token: str,
    _secret_key: str | None = None,
) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Args:
        token: JWT string to decode.
        _secret_key: Override secret key (for testing only).

    Returns:
        Decoded claims dictionary.

    Raises:
        JWTError: If the token is expired, malformed, or has invalid signature.
    """
    key = _secret_key or _get_jwt_secret()
    return jwt.decode(token, key, algorithms=["HS256"])


# ── TOTP 2FA ─────────────────────────────────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a random base32 TOTP secret.

    Returns:
        Base32-encoded secret string.
    """
    import pyotp

    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Generate an otpauth:// URI for the TOTP secret.

    Args:
        secret: Base32 TOTP secret.
        email: User email for the URI label.

    Returns:
        otpauth:// URI string.
    """
    import pyotp

    return pyotp.TOTP(secret).provisioning_uri(
        name=email, issuer_name="activia-trace"
    )


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret.

    Args:
        secret: Base32 TOTP secret.
        code: 6-digit TOTP code to verify.

    Returns:
        True if the code is valid, False otherwise.
    """
    import pyotp

    totp = pyotp.TOTP(secret)
    return totp.verify(code)


# ── Opaque tokens (refresh + password reset) ─────────────────────────────────


def generate_opaque_token() -> str:
    """Generate a cryptographically secure opaque token.

    The token is 64 random bytes encoded as a 128-char hex string.

    Returns:
        128-character hex string.
    """
    return os.urandom(64).hex()


def hash_token(token: str) -> str:
    """Hash an opaque token with SHA256 for storage.

    Args:
        token: The opaque token string.

    Returns:
        SHA256 hex digest (64 characters).
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()
