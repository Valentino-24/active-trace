"""Tests for security utilities: JWT, Argon2id, TOTP, opaque tokens.

RED→GREEN→TRIANGULATE: security/core functions.

NOTE: These tests set env vars for Settings. For structural/unit tests,
the test doesn't need a real DB — Settings just needs to be loadable.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import timedelta

import pytest
from jose import JWTError

# Set env vars BEFORE importing security module so Settings() can load
os.environ["DATABASE_URL"] = "postgresql+asyncpg://u:p@localhost:5432/t"
os.environ["SECRET_KEY"] = "a-32-char-test-secret-key-for-testing-only!!"
os.environ["ENCRYPTION_KEY"] = "a-32-char-test-encryption-key-for-testing!!"

from app.core.security import (  # noqa: E402
    create_access_token,
    create_impersonation_token,
    decode_access_token,
    generate_opaque_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)

# Test secret key (32+ chars, matches the env-var value above)
TEST_SECRET_KEY = "a-32-char-test-secret-key-for-testing-only!!"


class TestPasswordHashing:
    """RED→GREEN: Argon2id password hashing."""

    def test_hash_password_returns_string(self):
        """hash_password returns a non-empty string."""
        hashed = hash_password("secure_password_123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """verify_password returns True for correct password."""
        hashed = hash_password("secure_password_123")
        assert verify_password("secure_password_123", hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password returns False for wrong password."""
        hashed = hash_password("secure_password_123")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_is_different_each_time(self):
        """Same password produces different hash each time (salt)."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2


class TestAccessToken:
    """RED→GREEN: JWT access token creation and decoding."""

    def test_create_access_token_returns_string(self):
        """create_access_token returns a JWT string."""
        token = create_access_token(
            data={"sub": "user-uuid", "tenant_id": "tenant-uuid", "roles": []}
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        """decode_access_token returns the original claims."""
        data = {"sub": "user-123", "tenant_id": "tenant-456", "roles": ["admin"]}
        token = create_access_token(data=data)
        decoded = decode_access_token(token)
        assert decoded["sub"] == "user-123"
        assert decoded["tenant_id"] == "tenant-456"
        assert decoded["roles"] == ["admin"]

    def test_token_has_standard_claims(self):
        """Token includes exp, iat, and jti claims."""
        data = {"sub": "user-1", "tenant_id": "tenant-1", "roles": []}
        token = create_access_token(data=data)
        decoded = decode_access_token(token)
        assert "exp" in decoded
        assert "iat" in decoded
        assert "jti" in decoded

    def test_decode_expired_token_raises(self):
        """decode_access_token raises JWTError for expired token."""
        data = {"sub": "user-1", "tenant_id": "tenant-1", "roles": []}
        token = create_access_token(data=data, expires_delta=timedelta(seconds=-60))
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_decode_invalid_signature_raises(self):
        """Token signed with different key raises JWTError."""
        other_key = "diff-key-that-is-32-chars-long-for-testing!!"
        token = create_access_token(
            data={"sub": "user-1", "tenant_id": "tenant-1", "roles": []},
            _secret_key=other_key,
        )
        with pytest.raises(JWTError):
            decode_access_token(token)


class TestTotp:
    """RED→GREEN: TOTP 2FA utilities."""

    def test_generate_totp_secret_returns_base32(self):
        """generate_totp_secret returns a base32 string."""
        secret = generate_totp_secret()
        assert isinstance(secret, str)
        assert len(secret) > 0
        # Base32 chars: A-Z, 2-7
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_get_totp_uri_contains_otpauth(self):
        """get_totp_uri returns an otpauth:// URI."""
        import urllib.parse

        secret = generate_totp_secret()
        uri = get_totp_uri(secret, "test@example.com")
        assert uri.startswith("otpauth://")
        # Email is URL-encoded, so check decoded or partial
        assert "activia-trace" in uri
        decoded = urllib.parse.unquote(uri)
        assert "test@example.com" in decoded

    def test_verify_totp_valid_code(self):
        """verify_totp returns True for a valid TOTP code."""
        secret = generate_totp_secret()
        import pyotp

        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert verify_totp(secret, code) is True

    def test_verify_totp_invalid_code(self):
        """verify_totp returns False for an invalid code."""
        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False


class TestImpersonationToken:
    """RED→GREEN: Impersonation token creation."""

    def test_create_impersonation_token_has_impersonator_id(self):
        """Impersonation token contains impersonator_id claim."""
        user_id = uuid.uuid4()
        impersonator_id = uuid.uuid4()

        token = create_impersonation_token(
            user_id=user_id,
            impersonator_id=impersonator_id,
            tenant_id=uuid.uuid4(),
            _secret_key=TEST_SECRET_KEY,
        )
        payload = decode_access_token(token, _secret_key=TEST_SECRET_KEY)

        assert payload["sub"] == str(user_id)
        assert payload["impersonator_id"] == str(impersonator_id)
        assert payload["purpose"] == "impersonation"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_create_impersonation_token_includes_tenant_id(self):
        """Impersonation token includes tenant_id from impersonated user."""
        tenant_id = uuid.uuid4()
        token = create_impersonation_token(
            user_id=uuid.uuid4(),
            impersonator_id=uuid.uuid4(),
            tenant_id=tenant_id,
            _secret_key=TEST_SECRET_KEY,
        )
        payload = decode_access_token(token, _secret_key=TEST_SECRET_KEY)
        assert payload["tenant_id"] == str(tenant_id)


class TestOpaqueToken:
    """RED→GREEN: Opaque token generation and hashing."""

    def test_generate_opaque_token_returns_hex(self):
        """generate_opaque_token returns a 128-char hex string (64 bytes)."""
        token = generate_opaque_token()
        assert isinstance(token, str)
        assert len(token) == 128  # 64 bytes = 128 hex chars
        # All hex chars
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_opaque_token_is_unique(self):
        """Two calls produce different tokens."""
        t1 = generate_opaque_token()
        t2 = generate_opaque_token()
        assert t1 != t2

    def test_hash_token_returns_sha256(self):
        """hash_token returns a 64-char hex string (SHA256)."""
        token = "some-random-token-value"
        hashed = hash_token(token)
        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA256 = 64 hex chars

    def test_hash_token_is_deterministic(self):
        """Same input produces same hash."""
        token = "deterministic-test-token-123"
        h1 = hash_token(token)
        h2 = hash_token(token)
        assert h1 == h2

    def test_hash_token_different_for_different_inputs(self):
        """Different inputs produce different hashes."""
        h1 = hash_token("token-a")
        h2 = hash_token("token-b")
        assert h1 != h2
