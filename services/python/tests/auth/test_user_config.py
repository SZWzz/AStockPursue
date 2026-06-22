"""Tests for per-user LLM/data-source configuration.

Covers:
- encrypt_config / decrypt_config round-trip
- decrypt_config with non-encrypted field (backward compat)
- Different sensitive_fields
- ContextVar isolation between contexts
- load_user_config (mock DB)
- get_current_user_config / get_current_user_id
- clear_user_config
- ENV_KEYS constant
"""

from __future__ import annotations

import contextvars
import os
from unittest.mock import MagicMock

import pytest

from src.db.crypto import decrypt_password, encrypt_password, generate_key_b64


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_db_conn(return_row: tuple | None = None) -> MagicMock:
    """Create a mock DB connection that returns `return_row` on fetchone."""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = return_row

    conn.cursor.return_value = cursor
    return conn


# ---------------------------------------------------------------------------
# encrypt_config / decrypt_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_encrypt_decrypt_roundtrip():
    """encrypt_config then decrypt_config restores original values."""
    from src.auth.user_config import decrypt_config, encrypt_config

    sensitivity = {"api_key", "secret"}
    original = {"api_key": "sk-abc123", "secret": "super-secret", "model": "gpt-4"}

    encrypted = encrypt_config(original, sensitivity)
    # encrypted fields should be different from original
    assert encrypted["api_key"] != "sk-abc123"
    assert encrypted["secret"] != "super-secret"
    # non-sensitive field unchanged
    assert encrypted["model"] == "gpt-4"

    decrypted = decrypt_config(encrypted, sensitivity)
    assert decrypted["api_key"] == "sk-abc123"
    assert decrypted["secret"] == "super-secret"
    assert decrypted["model"] == "gpt-4"


@pytest.mark.unit
def test_decrypt_config_plain_text_field_skipped():
    """decrypt_config silently skips non-encrypted fields (backward compat)."""
    from src.auth.user_config import decrypt_config

    sensitivity = {"api_key"}
    config = {"api_key": "plain-text-not-encrypted", "model": "gpt-4"}

    result = decrypt_config(config, sensitivity)
    # Plain text should pass through (decryption fails silently, field kept as-is)
    assert result["api_key"] == "plain-text-not-encrypted"
    assert result["model"] == "gpt-4"


@pytest.mark.unit
def test_encrypt_config_empty():
    """encrypt_config returns empty dict as-is."""
    from src.auth.user_config import encrypt_config

    result = encrypt_config({}, {"api_key"})
    assert result == {}


@pytest.mark.unit
def test_decrypt_config_empty():
    """decrypt_config returns empty dict as-is."""
    from src.auth.user_config import decrypt_config

    result = decrypt_config({}, {"api_key"})
    assert result == {}


@pytest.mark.unit
def test_encrypt_config_none_field():
    """encrypt_config skips fields with None/falsy value."""
    from src.auth.user_config import encrypt_config

    config = {"api_key": "", "secret": None, "model": "gpt-4"}
    result = encrypt_config(config, {"api_key", "secret"})
    assert result["api_key"] == ""  # empty not encrypted
    assert result["secret"] is None
    assert result["model"] == "gpt-4"


@pytest.mark.unit
def test_different_sensitive_fields():
    """Only specified sensitive_fields are encrypted."""
    from src.auth.user_config import decrypt_config, encrypt_config

    sensitivity_a = {"api_key"}
    sensitivity_b = {"tushare_token"}

    original = {"api_key": "key-abc", "tushare_token": "token-xyz", "model": "gpt-4"}

    encrypted = encrypt_config(original, sensitivity_a)
    # Only api_key encrypted
    assert encrypted["api_key"] != "key-abc"
    assert encrypted["tushare_token"] == "token-xyz"

    decrypted = decrypt_config(encrypted, sensitivity_a)
    assert decrypted["api_key"] == "key-abc"

    # Now encrypt with different fields
    encrypted_b = encrypt_config(original, sensitivity_b)
    assert encrypted_b["tushare_token"] != "token-xyz"
    assert encrypted_b["api_key"] == "key-abc"


# ---------------------------------------------------------------------------
# ContextVar isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_contextvar_isolation():
    """Setting user config in one context does not affect another."""
    from src.auth.user_config import (
        _current_user_config,
        _current_user_id,
        get_current_user_config,
        get_current_user_id,
    )

    config_a = {"llm": {"provider": "openai"}, "data_source": {}}
    config_b = {"llm": {"provider": "deepseek"}, "data_source": {}}

    ctx_a = contextvars.copy_context()
    ctx_b = contextvars.copy_context()

    ctx_a.run(_current_user_config.set, config_a)
    ctx_a.run(_current_user_id.set, 42)

    ctx_b.run(_current_user_config.set, config_b)
    ctx_b.run(_current_user_id.set, 99)

    result_a = ctx_a.run(get_current_user_config)
    result_b = ctx_b.run(get_current_user_config)
    id_a = ctx_a.run(get_current_user_id)
    id_b = ctx_b.run(get_current_user_id)

    assert result_a == config_a
    assert result_b == config_b
    assert id_a == 42
    assert id_b == 99


# ---------------------------------------------------------------------------
# load_user_config (mock DB)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_load_user_config_returns_llm_and_data_source(monkeypatch: pytest.MonkeyPatch):
    """load_user_config returns dict with llm and data_source keys."""
    from src.auth.user_config import load_user_config

    # Mock get_connection to return a user row with encrypted configs
    key = generate_key_b64()
    monkeypatch.setenv("USER_CONFIG_ENCRYPTION_KEY", key)

    enc_api_key = encrypt_password("sk-test-123", key)
    enc_tushare = encrypt_password("tushare-token-abc", key)

    row = (
        {"provider": "openai", "model": "gpt-4", "api_key": enc_api_key},
        {"tushare_token": enc_tushare},
    )

    conn = _mock_db_conn(return_row=row)

    def mock_get_connection():
        return conn

    # get_connection is imported inside load_user_config via
    #   from src.db.pool import get_connection
    monkeypatch.setattr("src.db.pool.get_connection", mock_get_connection)

    result = load_user_config(1)

    assert isinstance(result, dict)
    assert "llm" in result
    assert "data_source" in result
    assert result["llm"]["provider"] == "openai"
    assert result["llm"]["model"] == "gpt-4"
    # api_key should be decrypted
    assert result["llm"]["api_key"] == "sk-test-123"
    assert result["data_source"]["tushare_token"] == "tushare-token-abc"


@pytest.mark.unit
def test_load_user_config_no_user_returns_empty(monkeypatch: pytest.MonkeyPatch):
    """load_user_config returns {} when no user row is found."""
    from src.auth.user_config import load_user_config

    conn = _mock_db_conn(return_row=None)
    monkeypatch.setattr("src.db.pool.get_connection", lambda: conn)

    result = load_user_config(999)
    assert result == {}


@pytest.mark.unit
def test_load_user_config_db_error_returns_empty(monkeypatch: pytest.MonkeyPatch):
    """load_user_config returns {} when DB raises an exception."""
    from src.auth.user_config import load_user_config

    def failing_connection():
        raise RuntimeError("DB connection failed")

    monkeypatch.setattr("src.db.pool.get_connection", failing_connection)

    result = load_user_config(1)
    assert result == {}


@pytest.mark.unit
def test_load_user_config_non_dict_columns(monkeypatch: pytest.MonkeyPatch):
    """load_user_config handles non-dict JSONB columns gracefully."""
    from src.auth.user_config import load_user_config

    row = ("not-a-dict", ["list-not-dict"])

    conn = _mock_db_conn(return_row=row)
    monkeypatch.setattr("src.db.pool.get_connection", lambda: conn)

    result = load_user_config(1)
    assert isinstance(result, dict)
    assert result["llm"] == {}
    assert result["data_source"] == {}


# ---------------------------------------------------------------------------
# get_current_user_config / get_current_user_id / clear_user_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_current_user_config_returns_none_initially():
    """get_current_user_config returns None when nothing has been set."""
    from src.auth.user_config import get_current_user_config

    # Reset contextvar to default
    from src.auth.user_config import _current_user_config
    _current_user_config.set(None)

    assert get_current_user_config() is None


@pytest.mark.unit
def test_get_current_user_id_returns_none_initially():
    """get_current_user_id returns None when nothing has been set."""
    from src.auth.user_config import _current_user_id, get_current_user_id

    _current_user_id.set(None)
    assert get_current_user_id() is None


@pytest.mark.unit
def test_clear_user_config_resets_everything():
    """clear_user_config resets all config state to None."""
    from src.auth.user_config import (
        _current_user_config,
        _current_user_id,
        clear_user_config,
        get_current_user_config,
        get_current_user_id,
    )

    _current_user_config.set({"llm": {"provider": "test"}})
    _current_user_id.set(42)

    assert get_current_user_config() is not None
    assert get_current_user_id() == 42

    clear_user_config()

    assert get_current_user_config() is None
    assert get_current_user_id() is None


# ---------------------------------------------------------------------------
# ENV_KEYS constant
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_env_keys_contains_expected_count():
    """ENV_KEYS should contain exactly 11 keys."""
    from src.auth.user_config import _ENV_KEYS

    assert len(_ENV_KEYS) == 11


@pytest.mark.unit
def test_env_keys_contains_expected_names():
    """ENV_KEYS contains the expected environment variable names."""
    from src.auth.user_config import _ENV_KEYS

    expected = {
        "LANGCHAIN_PROVIDER", "LANGCHAIN_MODEL_NAME",
        "OPENAI_BASE_URL", "OPENAI_API_KEY",
        "TUSHARE_TOKEN",
        "OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE",
        "TWELVE_DATA_API_KEY", "FINNHUB_API_KEY", "TIINGO_API_KEY",
    }
    assert _ENV_KEYS == expected
