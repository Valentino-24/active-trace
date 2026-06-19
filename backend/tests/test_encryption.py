"""Tests for AES-256-GCM encryption in core/security.py.

Pure unit tests — no database required.
"""

import base64

import pytest
from cryptography.exceptions import InvalidTag

from app.core.security import KEY_LENGTH, decrypt, encrypt


@pytest.fixture
def enc_key() -> bytes:
    """32-byte test encryption key."""
    return b"a" * KEY_LENGTH


class TestEncryptRoundTrip:
    """RED→GREEN: encrypt → decrypt yields the original."""

    def test_round_trip_simple_string(self, enc_key):
        """Short text survives encrypt → decrypt cycle."""
        original = "hello world"
        encrypted = encrypt(original, enc_key)
        decrypted = decrypt(encrypted, enc_key)
        assert decrypted == original

    def test_round_trip_long_string(self, enc_key):
        """Long text survives encrypt → decrypt cycle."""
        original = "A" * 10_000
        encrypted = encrypt(original, enc_key)
        decrypted = decrypt(encrypted, enc_key)
        assert decrypted == original

    def test_round_trip_unicode(self, enc_key):
        """Unicode text (including emoji) survives round-trip."""
        original = "ñöú áéíóú 😀🔥 日本語"
        encrypted = encrypt(original, enc_key)
        decrypted = decrypt(encrypted, enc_key)
        assert decrypted == original

    def test_round_trip_empty_string(self, enc_key):
        """Empty string encrypts and decrypts successfully."""
        original = ""
        encrypted = encrypt(original, enc_key)
        decrypted = decrypt(encrypted, enc_key)
        assert decrypted == original


class TestDecryptErrors:
    """TRIANGULATE: decryption with wrong key or corrupt data fails."""

    def test_wrong_key_fails(self, enc_key):
        """Decrypt with a different key raises InvalidTag."""
        plaintext = "secret data"
        encrypted = encrypt(plaintext, enc_key)
        wrong_key = bytes(b for b in enc_key)  # copy
        wrong_key = bytes(b ^ 0x01 for b in wrong_key)  # flip bit
        with pytest.raises(InvalidTag):
            decrypt(encrypted, wrong_key)

    def test_corrupt_ciphertext_fails(self, enc_key):
        """Tampered base64 payload raises an error."""
        encrypted = encrypt("important", enc_key)
        # Flip a byte in the ciphertext portion
        raw = bytearray(base64.b64decode(encrypted))
        raw[len(raw) // 2] ^= 0xFF
        corrupted = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises((InvalidTag, ValueError)):
            decrypt(corrupted, enc_key)

    def test_invalid_base64_fails(self, enc_key):
        """Non-base64 input raises an error."""
        with pytest.raises((ValueError, Exception)):
            decrypt("not-base64!!!", enc_key)

    def test_truncated_payload_fails(self, enc_key):
        """Payload shorter than nonce + tag raises ValueError."""
        # 4 bytes is too short to be a valid GCM packet
        short_b64 = base64.b64encode(b"abcd").decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            decrypt(short_b64, enc_key)


class TestKeyValidation:
    """Key length validation."""

    def test_encrypt_with_short_key_raises(self):
        """Key shorter than 32 bytes raises ValueError."""
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            encrypt("test", b"short")

    def test_decrypt_with_short_key_raises(self, enc_key):
        """Key shorter than 32 bytes raises ValueError."""
        with pytest.raises(ValueError, match="exactly 32 bytes"):
            decrypt("dGVzdA==", b"short")

    def test_encrypt_output_is_base64(self, enc_key):
        """Encrypt output is a valid base64 ASCII string."""
        encrypted = encrypt("test", enc_key)
        assert isinstance(encrypted, str)
        # Verify it's valid base64 by decoding
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 0
