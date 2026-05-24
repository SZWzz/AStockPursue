"""Per-user LLM and data source configuration.

Loads user-specific settings from PostgreSQL and applies them as environment
variable overrides. Sensitive fields (API keys, tokens) are AES-256-GCM
encrypted at rest in the database.
"""

from __future__ import annotations

import logging
import os

from src.db.crypto import decrypt_password, encrypt_password, generate_key_b64

logger = logging.getLogger(__name__)

_ACTIVE_USER_CONFIG: dict | None = None
_ACTIVE_USER_ID: int | None = None

# Fields that should be encrypted before storing in vt_users.llm_config / data_source_config
_SENSITIVE_LLM_FIELDS = {"api_key"}
_SENSITIVE_DS_FIELDS = {"tushare_token", "okx_api_key", "okx_secret_key", "okx_passphrase"}


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
                # Field might not be encrypted (plain text, old data)
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

    _ACTIVE_USER_CONFIG = {"llm": llm_cfg, "data_source": ds_cfg}
    _ACTIVE_USER_ID = user_id

    logger.info("Loaded config for user %s: provider=%s model=%s tushare=%s",
                user_id,
                llm_cfg.get("provider", "default"),
                llm_cfg.get("model", "default"),
                "configured" if ds_cfg.get("tushare_token") else "not set")
    return _ACTIVE_USER_CONFIG


def clear_user_config() -> None:
    """Clear active user config overrides."""
    global _ACTIVE_USER_CONFIG, _ACTIVE_USER_ID
    _ACTIVE_USER_CONFIG = None
    _ACTIVE_USER_ID = None
