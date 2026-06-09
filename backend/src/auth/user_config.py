"""Per-user LLM and data source configuration.

Loads user-specific settings from PostgreSQL and applies them as environment
variable overrides. Sensitive fields (API keys, tokens) are AES-256-GCM
encrypted at rest in the database.
"""

from __future__ import annotations

import contextvars
import logging
import os

from src.db.crypto import decrypt_password, encrypt_password, generate_key_b64

logger = logging.getLogger(__name__)

# ── Per-request context (contextvars) ──────────────────────────────────
# These avoid the cross-request os.environ leak that plagued the old design.
# Middleware in api_server.py saves/restores os.environ per-request.
_current_user_config: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "user_config", default=None
)
_current_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "user_id", default=None
)

# Keys managed per-request in os.environ — middleware saves/restores these
# so concurrent requests don't leak credentials across each other.
_ENV_KEYS: set[str] = {
    "LANGCHAIN_PROVIDER", "LANGCHAIN_MODEL_NAME",
    "OPENAI_BASE_URL", "OPENAI_API_KEY",
    "TUSHARE_TOKEN",
    "OKX_API_KEY", "OKX_SECRET_KEY", "OKX_PASSPHRASE",
    "TWELVE_DATA_API_KEY", "FINNHUB_API_KEY", "TIINGO_API_KEY",
}

# Legacy global state (deprecated, kept for backward compatibility)
_ACTIVE_USER_CONFIG: dict | None = None
_ACTIVE_USER_ID: int | None = None

# Fields that should be encrypted before storing in vt_users.llm_config / data_source_config
_SENSITIVE_LLM_FIELDS = {"api_key"}
_SENSITIVE_DS_FIELDS = {
    "tushare_token",
    "okx_api_key", "okx_secret_key", "okx_passphrase",
    "twelvedata_api_key",
    "finnhub_api_key",
    "tiingo_api_key",
}


def _get_encryption_key() -> bytes:
    """Get or generate the user config encryption key."""
    key = os.getenv("USER_CONFIG_ENCRYPTION_KEY", "")
    if not key:
        key = generate_key_b64()
        os.environ["USER_CONFIG_ENCRYPTION_KEY"] = key
        logger.warning("Generated new USER_CONFIG_ENCRYPTION_KEY — save this to .env for persistence")
    return key


def encrypt_config(config: dict, sensitive_fields: set) -> dict:
    """Encrypt sensitive fields in a config dict. Returns a new dict."""
    if not config:
        return config
    key = _get_encryption_key()
    result = dict(config)
    for field in sensitive_fields:
        if result.get(field):
            try:
                result[field] = encrypt_password(str(result[field]), key)
            except Exception as e:
                logger.warning("Failed to encrypt field %s: %s", field, e)
    return result


def decrypt_config(config: dict, sensitive_fields: set) -> dict:
    """Decrypt sensitive fields in a config dict. Returns a new dict."""
    if not config:
        return config
    key = _get_encryption_key()
    result = dict(config)
    for field in sensitive_fields:
        if result.get(field):
            try:
                result[field] = decrypt_password(str(result[field]), key)
            except Exception:
                logger.debug("Field %s not encrypted (plain text or old data), skipping decryption", field)
                pass
    return result


def load_user_config(user_id: int) -> dict:
    """Load LLM and data source config for a user from the database.

    Decrypts encrypted fields and applies overrides to os.environ.
    """
    global _ACTIVE_USER_CONFIG, _ACTIVE_USER_ID

    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT llm_config, data_source_config FROM vt_users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {}

                llm_cfg = row[0] if isinstance(row[0], dict) else {}
                ds_cfg = row[1] if isinstance(row[1], dict) else {}
    except Exception as e:
        logger.warning("Failed to load user config for user %s: %s", user_id, e)
        return {}

    # Decrypt sensitive fields
    llm_cfg = decrypt_config(llm_cfg, _SENSITIVE_LLM_FIELDS)
    ds_cfg = decrypt_config(ds_cfg, _SENSITIVE_DS_FIELDS)

    # Apply LLM overrides to environment
    if llm_cfg.get("provider"):
        os.environ["LANGCHAIN_PROVIDER"] = llm_cfg["provider"]
    if llm_cfg.get("model"):
        os.environ["LANGCHAIN_MODEL_NAME"] = llm_cfg["model"]
    if llm_cfg.get("base_url"):
        os.environ["OPENAI_BASE_URL"] = llm_cfg["base_url"]
    if llm_cfg.get("api_key"):
        os.environ["OPENAI_API_KEY"] = llm_cfg["api_key"]

    # Apply data source overrides
    if ds_cfg.get("tushare_token"):
        os.environ["TUSHARE_TOKEN"] = ds_cfg["tushare_token"]
    if ds_cfg.get("okx_api_key"):
        os.environ["OKX_API_KEY"] = ds_cfg["okx_api_key"]
        os.environ["OKX_SECRET_KEY"] = ds_cfg.get("okx_secret_key", "")
        os.environ["OKX_PASSPHRASE"] = ds_cfg.get("okx_passphrase", "")
    if ds_cfg.get("twelvedata_api_key"):
        os.environ["TWELVE_DATA_API_KEY"] = ds_cfg["twelvedata_api_key"]
    if ds_cfg.get("finnhub_api_key"):
        os.environ["FINNHUB_API_KEY"] = ds_cfg["finnhub_api_key"]
    if ds_cfg.get("tiingo_api_key"):
        os.environ["TIINGO_API_KEY"] = ds_cfg["tiingo_api_key"]

    _ACTIVE_USER_CONFIG = {"llm": llm_cfg, "data_source": ds_cfg}
    _ACTIVE_USER_ID = user_id

    # Store in contextvars for per-request access
    _current_user_config.set(_ACTIVE_USER_CONFIG)
    _current_user_id.set(user_id)

    logger.info("Loaded config for user %s: provider=%s model=%s tushare=%s twelvedata=%s",
                user_id,
                llm_cfg.get("provider", "default"),
                llm_cfg.get("model", "default"),
                "configured" if ds_cfg.get("tushare_token") else "not set",
                "configured" if ds_cfg.get("twelvedata_api_key") else "not set")
    return _ACTIVE_USER_CONFIG


def get_current_user_config() -> dict | None:
    """Get the current request's user config from contextvars.

    Returns None if no user config has been loaded for this request.
    Preferred over reading os.environ directly.
    """
    return _current_user_config.get()


def get_current_user_id() -> int | None:
    """Get the current request's user ID from contextvars."""
    return _current_user_id.get()


def clear_user_config() -> None:
    """Clear active user config overrides (both legacy globals and contextvars)."""
    global _ACTIVE_USER_CONFIG, _ACTIVE_USER_ID
    _ACTIVE_USER_CONFIG = None
    _ACTIVE_USER_ID = None
    _current_user_config.set(None)
    _current_user_id.set(None)
