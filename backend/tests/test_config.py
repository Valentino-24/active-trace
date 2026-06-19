"""Tests for core.config — Settings."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
    "SECRET_KEY": "a-secret-key-that-is-at-least-32-characters-long!!",
    "ENCRYPTION_KEY": "an-encryption-key-that-is-at-least-32-characters!!",
}

# Save original env vars so we can restore them
_ORIG_SECRET_KEY = os.environ.get("SECRET_KEY")
_ORIG_ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")


def _clear_env_keys():
    """Temporarily remove SECRET_KEY/ENCRYPTION_KEY from real env."""
    os.environ.pop("SECRET_KEY", None)
    os.environ.pop("ENCRYPTION_KEY", None)


def _restore_env_keys():
    """Restore SECRET_KEY/ENCRYPTION_KEY after test."""
    if _ORIG_SECRET_KEY is not None:
        os.environ["SECRET_KEY"] = _ORIG_SECRET_KEY
    if _ORIG_ENCRYPTION_KEY is not None:
        os.environ["ENCRYPTION_KEY"] = _ORIG_ENCRYPTION_KEY


def _make_settings(env: dict) -> "Settings":
    """Instantiate Settings with given env dict, bypassing .env file."""
    from app.core.config import Settings

    return Settings(_env_file=None, **env)


class TestSettings:
    """RED→GREEN→TRIANGULATE: Settings validation."""

    def test_settings_with_valid_env(self):
        """Settings instantiates with all required vars and custom ACCESS_TOKEN_EXPIRE_MINUTES."""
        env = dict(REQUIRED_ENV, ACCESS_TOKEN_EXPIRE_MINUTES="30")
        settings = _make_settings(env)
        assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
        assert settings.secret_key == REQUIRED_ENV["SECRET_KEY"]
        assert settings.encryption_key == REQUIRED_ENV["ENCRYPTION_KEY"]
        assert settings.access_token_expire_minutes == 30

    def test_settings_default_access_token_expire(self):
        """ACCESS_TOKEN_EXPIRE_MINUTES defaults to 15 when not set."""
        env = dict(REQUIRED_ENV)
        settings = _make_settings(env)
        assert settings.access_token_expire_minutes == 15

    def test_settings_missing_secret_key_raises(self):
        """Missing SECRET_KEY raises ValidationError."""
        _clear_env_keys()
        env = dict(REQUIRED_ENV)
        del env["SECRET_KEY"]
        with pytest.raises(ValidationError):
            _make_settings(env)
        _restore_env_keys()

    def test_settings_short_secret_key_raises(self):
        """SECRET_KEY shorter than 32 chars raises ValidationError."""
        _clear_env_keys()
        env = dict(REQUIRED_ENV, SECRET_KEY="short")
        with pytest.raises(ValidationError):
            _make_settings(env)
        _restore_env_keys()

    def test_settings_short_encryption_key_raises(self):
        """ENCRYPTION_KEY shorter than 32 chars raises ValidationError."""
        _clear_env_keys()
        env = dict(REQUIRED_ENV, ENCRYPTION_KEY="short")
        with pytest.raises(ValidationError):
            _make_settings(env)
        _restore_env_keys()

    def test_settings_empty_database_url_raises(self):
        """Empty DATABASE_URL raises ValidationError."""
        env = dict(REQUIRED_ENV, DATABASE_URL="")
        with pytest.raises(ValidationError):
            _make_settings(env)
