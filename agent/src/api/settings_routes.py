"""Settings HTTP routes: LLM, data sources, skills, MCP."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.auth.dependencies import require_auth as _require_auth
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, UploadFile, status
from pydantic import BaseModel, Field

from src.api.common import ENV_PATH, ENV_EXAMPLE_PATH, AGENT_DIR, LLM_PROVIDER_CONFIG_PATH
from src.api.common import LLM_API_KEY_PLACEHOLDERS, TUSHARE_TOKEN_PLACEHOLDERS

# ============================================================================
# Pydantic Models
# ============================================================================


class LLMProviderOption(BaseModel):
    """Supported LLM provider metadata for the settings UI."""

    name: str
    label: str
    api_key_env: Optional[str] = None
    base_url_env: str
    default_model: str
    default_base_url: str
    api_key_required: bool = True
    auth_type: str = "api_key"
    login_command: Optional[str] = None


class LLMSettingsResponse(BaseModel):
    """Current LLM runtime settings."""

    provider: str
    model_name: str
    base_url: str
    api_key_env: Optional[str] = None
    api_key_configured: bool
    api_key_hint: Optional[str] = None
    api_key_required: bool
    temperature: float
    timeout_seconds: int
    max_retries: int
    reasoning_effort: str
    env_path: str
    providers: List[LLMProviderOption]


class UpdateLLMSettingsRequest(BaseModel):
    """Update LLM settings persisted to agent/.env."""

    provider: str = Field(..., min_length=1)
    model_name: str = Field(..., min_length=1)
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False
    temperature: float = 0.0
    timeout_seconds: int = Field(120, ge=1, le=3600)
    max_retries: int = Field(2, ge=0, le=20)
    reasoning_effort: Optional[str] = None


class DataSourceSettingsResponse(BaseModel):
    """Current data source credential settings."""

    # Credential-based sources
    tushare_token_configured: bool
    tushare_token_hint: Optional[str] = None
    okx_api_key_configured: bool = False
    okx_secret_key_configured: bool = False
    okx_passphrase_configured: bool = False
    twelvedata_api_key_configured: bool = False
    finnhub_api_key_configured: bool = False
    tiingo_api_key_configured: bool = False
    akshare_available: bool = False
    akshare_version: str = ""

    # Legacy single-loader booleans (keep for back-compat)
    yfinance_available: bool = False
    tencent_available: bool = False
    ccxt_available: bool = False
    coingecko_available: bool = False
    futu_available: bool = False
    global_indices_available: bool = False
    commodities_available: bool = False

    # New A-share loaders (Phase 2)
    mootdx_available: bool = False
    eastmoney_available: bool = False
    baidu_available: bool = False

    # Dynamic list of ALL registered loaders (for frontend dropdowns)
    loaders: list[dict] = []

    env_path: str


class UpdateDataSourceSettingsRequest(BaseModel):
    """Update data source credentials (stored encrypted in DB)."""

    tushare_token: Optional[str] = None
    clear_tushare_token: bool = False
    okx_api_key: Optional[str] = None
    okx_secret_key: Optional[str] = None
    okx_passphrase: Optional[str] = None
    clear_okx: bool = False
    twelvedata_api_key: Optional[str] = None
    clear_twelvedata: bool = False
    finnhub_api_key: Optional[str] = None
    clear_finnhub: bool = False
    tiingo_api_key: Optional[str] = None
    clear_tiingo: bool = False


# ============================================================================
# Helper Functions
# ============================================================================


def _load_llm_providers() -> List[LLMProviderOption]:
    """Load provider metadata from JSON so additions stay data-driven."""
    try:
        raw = json.loads(LLM_PROVIDER_CONFIG_PATH.read_text(encoding="utf-8"))
        providers = [LLMProviderOption(**item) for item in raw]
    except Exception as exc:
        raise RuntimeError(f"Failed to load LLM provider config: {LLM_PROVIDER_CONFIG_PATH}") from exc

    seen: set[str] = set()
    for provider in providers:
        if provider.name in seen:
            raise RuntimeError(f"Duplicate LLM provider name: {provider.name}")
        seen.add(provider.name)
    if not providers:
        raise RuntimeError("LLM provider config must not be empty")
    return providers


LLM_PROVIDERS = _load_llm_providers()
LLM_PROVIDER_BY_NAME = {provider.name: provider for provider in LLM_PROVIDERS}
LLM_REASONING_EFFORTS = {"", "low", "medium", "high", "max"}


def _ensure_agent_env_file() -> Path:
    """Ensure the project-local agent/.env exists."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text("# Created by AStockPursue Web UI settings.\n", encoding="utf-8")
    return ENV_PATH


def _strip_env_value(value: str) -> str:
    """Remove basic dotenv quotes and inline comments."""
    value = value.strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _read_env_values(path: Path) -> Dict[str, str]:
    """Read active KEY=value entries from a dotenv file."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = _strip_env_value(value)
    return values


def _read_settings_env_values() -> Dict[str, str]:
    """Read settings without creating agent/.env.

    Prefer the user's active agent/.env. If it does not exist yet, fall back to
    agent/.env.example for display defaults only.
    """
    if ENV_PATH.exists():
        return _read_env_values(ENV_PATH)
    if ENV_EXAMPLE_PATH.exists():
        return _read_env_values(ENV_EXAMPLE_PATH)
    return {}


def _project_relative_path(path: Path) -> str:
    """Return a project-relative display path without leaking an absolute path."""
    try:
        return path.resolve().relative_to(AGENT_DIR.parent.resolve()).as_posix()
    except ValueError:
        return path.name


def _format_env_value(value: str) -> str:
    """Format a dotenv value without allowing multiline injection."""
    if "\n" in value or "\r" in value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Environment values cannot contain newlines")
    value = value.strip()
    if not value:
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _write_env_values(path: Path, updates: Dict[str, str]) -> None:
    """Upsert active dotenv values while preserving comments and ordering."""
    _ensure_agent_env_file()
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    for index, raw in enumerate(lines):
        stripped = raw.lstrip()
        is_comment = stripped.startswith("#")
        candidate = stripped[1:].lstrip() if is_comment else stripped
        if "=" not in candidate:
            continue
        key = candidate.split("=", 1)[0].strip()
        if key in updates and key not in seen:
            lines[index] = f"{key}={_format_env_value(updates[key])}"
            seen.add(key)
    missing = [key for key in updates if key not in seen]
    if missing:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append("# Updated from Web UI")
        for key in missing:
            lines.append(f"{key}={_format_env_value(updates[key])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _is_configured_secret(value: str, placeholders: set[str]) -> bool:
    """Return True when a secret is set and not a documented placeholder."""
    normalized = value.strip().strip('"').strip("'")
    if not normalized:
        return False
    return normalized.lower() not in {placeholder.lower() for placeholder in placeholders}


def _coerce_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_llm_settings_response(values: Optional[Dict[str, str]] = None, *, db_config: Optional[dict] = None) -> LLMSettingsResponse:
    """Build the public settings payload, preferring DB config over dotenv."""
    env_values = values if values is not None else _read_settings_env_values()
    db = db_config or {}

    provider_name = db.get("provider") or env_values.get("LANGCHAIN_PROVIDER", "openai").strip().lower()
    provider = LLM_PROVIDER_BY_NAME.get(provider_name, LLM_PROVIDER_BY_NAME["openai"])

    api_key = db.get("api_key", "") if db else env_values.get(provider.api_key_env or "", "")
    api_key_configured = bool(api_key) and _is_configured_secret(api_key, LLM_API_KEY_PLACEHOLDERS)
    api_key_hint = None
    if provider.auth_type == "oauth":
        try:
            from src.providers.openai_codex import get_openai_codex_login_status
            token = get_openai_codex_login_status()
        except Exception:
            token = None
        api_key_configured = bool(token)
        api_key_hint = None

    model_name = db.get("model") or env_values.get("LANGCHAIN_MODEL_NAME", provider.default_model)
    base_url = db.get("base_url") or env_values.get(provider.base_url_env, provider.default_base_url)
    temperature = db.get("temperature") if db.get("temperature") is not None else _coerce_float(env_values.get("LANGCHAIN_TEMPERATURE", "0.0"), 0.0)
    timeout_seconds = db.get("timeout_seconds") if db.get("timeout_seconds") is not None else _coerce_int(env_values.get("TIMEOUT_SECONDS", "120"), 120)
    max_retries = db.get("max_retries") if db.get("max_retries") is not None else _coerce_int(env_values.get("MAX_RETRIES", "2"), 2)
    reasoning_effort = db.get("reasoning_effort") if "reasoning_effort" in db else env_values.get("LANGCHAIN_REASONING_EFFORT", "").strip().lower()

    return LLMSettingsResponse(
        provider=provider.name,
        model_name=model_name,
        base_url=base_url,
        api_key_env=provider.api_key_env,
        api_key_configured=api_key_configured,
        api_key_hint=api_key_hint,
        api_key_required=provider.api_key_required,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        reasoning_effort=reasoning_effort,
        env_path=_project_relative_path(ENV_PATH),
        providers=LLM_PROVIDERS,
    )


def _build_data_source_settings_response(values: Optional[Dict[str, str]] = None, *, token: Optional[str] = None,
                                          okx_api_key: Optional[str] = None, okx_secret_key: Optional[str] = None,
                                          okx_passphrase: Optional[str] = None,
                                          twelvedata_api_key: Optional[str] = None,
                                          finnhub_api_key: Optional[str] = None,
                                          tiingo_api_key: Optional[str] = None) -> DataSourceSettingsResponse:
    """Build the public data source settings payload."""
    env_values = values if values is not None else _read_settings_env_values()
    if token is None:
        token = env_values.get("TUSHARE_TOKEN", "")
    token_configured = _is_configured_secret(token, TUSHARE_TOKEN_PLACEHOLDERS)
    okx_key_configured = bool(okx_api_key) if okx_api_key is not None else False
    okx_secret_configured = bool(okx_secret_key) if okx_secret_key is not None else False
    okx_pass_configured = bool(okx_passphrase) if okx_passphrase is not None else False
    td_configured = bool(twelvedata_api_key) if twelvedata_api_key is not None else False
    fh_configured = bool(finnhub_api_key) if finnhub_api_key is not None else False
    ti_configured = bool(tiingo_api_key) if tiingo_api_key is not None else False
    akshare_available = False
    akshare_version = ""
    try:
        import akshare
        akshare_available = True
        akshare_version = getattr(akshare, "__version__", "")
    except ImportError:
        pass

    # Free / no-auth loader availability — dynamically check ALL registered loaders
    yf_ok = tencent_ok = ccxt_ok = cg_ok = futu_ok = gi_ok = comm_ok = False
    mootdx_ok = eastmoney_ok = baidu_ok = False
    all_loaders: list[dict] = []

    try:
        from backtest.loaders.registry import LOADER_REGISTRY, _ensure_registered
        _ensure_registered()
        for name, cls in LOADER_REGISTRY.items():
            try:
                inst = cls()
                avail = inst.is_available() if hasattr(inst, "is_available") else True
            except Exception:
                avail = False

            # Legacy per-loader flags
            if name == "yfinance":      yf_ok = avail
            elif name == "tencent":     tencent_ok = avail
            elif name == "ccxt":        ccxt_ok = avail
            elif name == "coingecko":   cg_ok = avail
            elif name == "futu":        futu_ok = avail
            elif name == "global_indices": gi_ok = avail
            elif name == "commodities": comm_ok = avail
            elif name == "mootdx":      mootdx_ok = avail
            elif name == "eastmoney":   eastmoney_ok = avail
            elif name == "baidu":       baidu_ok = avail

            # Build dynamic loader entry for frontend
            all_loaders.append({
                "name": name,
                "display": getattr(cls, "name", name),
                "markets": sorted(getattr(cls, "markets", set())),
                "available": avail,
                "requires_auth": getattr(cls, "requires_auth", False),
            })
    except Exception:
        pass

    return DataSourceSettingsResponse(
        tushare_token_configured=token_configured,
        tushare_token_hint=None,
        okx_api_key_configured=okx_key_configured,
        okx_secret_key_configured=okx_secret_configured,
        okx_passphrase_configured=okx_pass_configured,
        twelvedata_api_key_configured=td_configured,
        finnhub_api_key_configured=fh_configured,
        tiingo_api_key_configured=ti_configured,
        akshare_available=akshare_available,
        akshare_version=akshare_version,
        yfinance_available=yf_ok,
        tencent_available=tencent_ok,
        ccxt_available=ccxt_ok,
        coingecko_available=cg_ok,
        futu_available=futu_ok,
        global_indices_available=gi_ok,
        commodities_available=comm_ok,
        mootdx_available=mootdx_ok,
        eastmoney_available=eastmoney_ok,
        baidu_available=baidu_ok,
        loaders=all_loaders,
        env_path=_project_relative_path(ENV_PATH),
    )


def _read_user_ds_config(user_id: int) -> dict:
    """Read and decrypt a user's data_source_config from the database."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import decrypt_config, _SENSITIVE_DS_FIELDS
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_source_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    return decrypt_config(dict(row[0]), _SENSITIVE_DS_FIELDS)
    except Exception:
        pass
    return {}


def _write_user_ds_config(user_id: int, updates: dict) -> bool:
    """Merge updates into a user's data_source_config, encrypt, and save to DB."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import encrypt_config, _SENSITIVE_DS_FIELDS
        import json

        # Read existing config, merge updates
        current = {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_source_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    current = dict(row[0])

        merged = {**current, **updates}
        encrypted = encrypt_config(merged, _SENSITIVE_DS_FIELDS)
        payload = json.dumps(encrypted)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET data_source_config = %s WHERE id = %s",
                    (payload, user_id),
                )
            conn.commit()
        return True
    except Exception:
        return False


def _read_user_llm_config(user_id: int) -> dict:
    """Read and decrypt a user's llm_config from the database."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import decrypt_config, _SENSITIVE_LLM_FIELDS
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT llm_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    return decrypt_config(dict(row[0]), _SENSITIVE_LLM_FIELDS)
    except Exception:
        pass
    return {}


def _write_user_llm_config(user_id: int, updates: dict) -> bool:
    """Merge updates into a user's llm_config, encrypt, and save to DB."""
    try:
        from src.db.pool import get_connection
        from src.auth.user_config import encrypt_config, _SENSITIVE_LLM_FIELDS
        import json

        current = {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT llm_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row and isinstance(row[0], dict):
                    current = dict(row[0])

        merged = {**current, **updates}
        encrypted = encrypt_config(merged, _SENSITIVE_LLM_FIELDS)
        payload = json.dumps(encrypted)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET llm_config = %s WHERE id = %s",
                    (payload, user_id),
                )
            conn.commit()
        return True
    except Exception:
        return False


def _apply_llm_config_to_env(llm_config: dict) -> None:
    """Apply a decrypted LLM config dict to os.environ."""
    if llm_config.get("provider"):
        os.environ["LANGCHAIN_PROVIDER"] = llm_config["provider"]
    if llm_config.get("model"):
        os.environ["LANGCHAIN_MODEL_NAME"] = llm_config["model"]
    if llm_config.get("base_url"):
        os.environ["OPENAI_BASE_URL"] = llm_config["base_url"]
    if llm_config.get("api_key"):
        os.environ["OPENAI_API_KEY"] = llm_config["api_key"]
    if llm_config.get("temperature") is not None:
        os.environ["LANGCHAIN_TEMPERATURE"] = str(llm_config["temperature"])
    if llm_config.get("timeout_seconds") is not None:
        os.environ["TIMEOUT_SECONDS"] = str(llm_config["timeout_seconds"])
    if llm_config.get("max_retries") is not None:
        os.environ["MAX_RETRIES"] = str(llm_config["max_retries"])
    if "reasoning_effort" in llm_config:
        os.environ["LANGCHAIN_REASONING_EFFORT"] = llm_config["reasoning_effort"]


def _sync_runtime_env(provider: LLMProviderOption, updates: Dict[str, str]) -> None:
    """Apply saved LLM settings to the running API process."""
    for key, value in updates.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    if provider.api_key_env:
        key_value = os.environ.get(provider.api_key_env, "")
        if _is_configured_secret(key_value, LLM_API_KEY_PLACEHOLDERS):
            os.environ["OPENAI_API_KEY"] = key_value
        else:
            os.environ.pop("OPENAI_API_KEY", None)
    elif provider.auth_type == "oauth":
        os.environ.pop("OPENAI_API_KEY", None)
    else:
        os.environ["OPENAI_API_KEY"] = "ollama"

    base_url = os.environ.get(provider.base_url_env, "")
    if base_url:
        os.environ["OPENAI_API_BASE"] = base_url
        os.environ["OPENAI_BASE_URL"] = base_url
    else:
        os.environ.pop("OPENAI_API_BASE", None)
        os.environ.pop("OPENAI_BASE_URL", None)


# ============================================================================
# Skill config helpers
# ============================================================================


def _read_skill_config(user_id: int) -> dict:
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT skill_config FROM vt_users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                return (row[0] or {}) if row else {}
    except Exception:
        return {}


def _write_skill_config(user_id: int, updates: dict) -> None:
    try:
        from src.db.pool import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vt_users SET skill_config = skill_config || %s::jsonb WHERE id = %s",
                    (json.dumps(updates), user_id),
                )
    except Exception:
        pass


# ============================================================================
# Router factory
# ============================================================================


router = APIRouter()

# ------------------------------------------------------------------------
# LLM settings
# ------------------------------------------------------------------------

@router.get(
    "/settings/llm",
    response_model=LLMSettingsResponse,
)
async def get_llm_settings(auth: dict = Depends(_require_auth)):
    """Return per-user LLM settings from the database (with .env fallback)."""
    user_id = auth["user_id"]
    db_config = _read_user_llm_config(user_id) if user_id > 0 else {}
    return _build_llm_settings_response(db_config=db_config)

@router.put("/settings/llm", response_model=LLMSettingsResponse)
async def update_llm_settings(payload: UpdateLLMSettingsRequest, auth: dict = Depends(_require_auth)):
    """Persist per-user LLM settings to the database (API key encrypted)."""
    user_id = auth["user_id"]
    provider_name = payload.provider.strip().lower()
    provider = LLM_PROVIDER_BY_NAME.get(provider_name)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported LLM provider")

    model_name = payload.model_name.strip()
    if not model_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model name is required")

    if payload.temperature < 0 or payload.temperature > 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Temperature must be between 0 and 2")

    reasoning_effort = (payload.reasoning_effort or "").strip().lower()
    if reasoning_effort not in LLM_REASONING_EFFORTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reasoning effort must be low, medium, high, or max")

    base_url = (payload.base_url if payload.base_url is not None else provider.default_base_url).strip()
    if provider.auth_type == "oauth":
        try:
            from src.providers.openai_codex import validate_codex_base_url
            base_url = validate_codex_base_url(base_url)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Build DB config dict
    db_updates: dict = {
        "provider": provider.name,
        "model": model_name,
        "base_url": base_url,
        "temperature": payload.temperature,
        "timeout_seconds": payload.timeout_seconds,
        "max_retries": payload.max_retries,
        "reasoning_effort": reasoning_effort,
    }

    if provider.api_key_env:
        if payload.clear_api_key:
            db_updates["api_key"] = ""
        elif payload.api_key is not None and payload.api_key.strip():
            db_updates["api_key"] = payload.api_key.strip()
    elif payload.clear_api_key:
        db_updates["api_key"] = ""

    if user_id > 0:
        _write_user_llm_config(user_id, db_updates)

    # Apply to runtime env
    _apply_llm_config_to_env(db_updates)

    return _build_llm_settings_response(db_config=db_updates)

# ------------------------------------------------------------------------
# Data source settings
# ------------------------------------------------------------------------

@router.get(
    "/settings/data-sources",
    response_model=DataSourceSettingsResponse,
)
async def get_data_source_settings(auth: dict = Depends(_require_auth)):
    """Return per-user data source credentials from the database."""
    user_id = auth["user_id"]
    ds_config = _read_user_ds_config(user_id) if user_id > 0 else {}
    return _build_data_source_settings_response(
        token=ds_config.get("tushare_token", ""),
        okx_api_key=ds_config.get("okx_api_key", ""),
        okx_secret_key=ds_config.get("okx_secret_key", ""),
        okx_passphrase=ds_config.get("okx_passphrase", ""),
        twelvedata_api_key=ds_config.get("twelvedata_api_key", ""),
        finnhub_api_key=ds_config.get("finnhub_api_key", ""),
        tiingo_api_key=ds_config.get("tiingo_api_key", ""),
    )

@router.put(
    "/settings/data-sources",
    response_model=DataSourceSettingsResponse,
)
async def update_data_source_settings(payload: UpdateDataSourceSettingsRequest, auth: dict = Depends(_require_auth)):
    """Persist per-user data source credentials to the database (encrypted)."""
    user_id = auth["user_id"]

    # Read existing DB config
    ds_config = _read_user_ds_config(user_id) if user_id > 0 else {}
    db_updates: dict = {}

    # --- Tushare ---
    if payload.clear_tushare_token:
        db_updates["tushare_token"] = ""
    elif payload.tushare_token is not None and payload.tushare_token.strip():
        db_updates["tushare_token"] = payload.tushare_token.strip()

    # --- OKX ---
    if payload.clear_okx:
        db_updates["okx_api_key"] = ""
        db_updates["okx_secret_key"] = ""
        db_updates["okx_passphrase"] = ""
    else:
        if payload.okx_api_key is not None:
            db_updates["okx_api_key"] = payload.okx_api_key.strip()
        if payload.okx_secret_key is not None:
            db_updates["okx_secret_key"] = payload.okx_secret_key.strip()
        if payload.okx_passphrase is not None:
            db_updates["okx_passphrase"] = payload.okx_passphrase.strip()

    # --- Twelve Data ---
    if payload.clear_twelvedata:
        db_updates["twelvedata_api_key"] = ""
    elif payload.twelvedata_api_key is not None and payload.twelvedata_api_key.strip():
        db_updates["twelvedata_api_key"] = payload.twelvedata_api_key.strip()

    # --- Finnhub ---
    if payload.clear_finnhub:
        db_updates["finnhub_api_key"] = ""
    elif payload.finnhub_api_key is not None and payload.finnhub_api_key.strip():
        db_updates["finnhub_api_key"] = payload.finnhub_api_key.strip()

    # --- Tiingo ---
    if payload.clear_tiingo:
        db_updates["tiingo_api_key"] = ""
    elif payload.tiingo_api_key is not None and payload.tiingo_api_key.strip():
        db_updates["tiingo_api_key"] = payload.tiingo_api_key.strip()

    if db_updates and user_id > 0:
        _write_user_ds_config(user_id, db_updates)

    # Apply to runtime env
    ds_config = _read_user_ds_config(user_id) if user_id > 0 else {}
    token = ds_config.get("tushare_token", "")
    okx_key = ds_config.get("okx_api_key", "")
    okx_secret = ds_config.get("okx_secret_key", "")
    okx_pass = ds_config.get("okx_passphrase", "")
    td_key = ds_config.get("twelvedata_api_key", "")
    fh_key = ds_config.get("finnhub_api_key", "")
    ti_key = ds_config.get("tiingo_api_key", "")

    if token and _is_configured_secret(token, TUSHARE_TOKEN_PLACEHOLDERS):
        os.environ["TUSHARE_TOKEN"] = token
    else:
        os.environ.pop("TUSHARE_TOKEN", None)

    if okx_key:
        os.environ["OKX_API_KEY"] = okx_key
        os.environ["OKX_SECRET_KEY"] = okx_secret
        os.environ["OKX_PASSPHRASE"] = okx_pass
    else:
        os.environ.pop("OKX_API_KEY", None)
        os.environ.pop("OKX_SECRET_KEY", None)
        os.environ.pop("OKX_PASSPHRASE", None)

    if td_key:
        os.environ["TWELVE_DATA_API_KEY"] = td_key
    else:
        os.environ.pop("TWELVE_DATA_API_KEY", None)

    if fh_key:
        os.environ["FINNHUB_API_KEY"] = fh_key
    else:
        os.environ.pop("FINNHUB_API_KEY", None)

    if ti_key:
        os.environ["TIINGO_API_KEY"] = ti_key
    else:
        os.environ.pop("TIINGO_API_KEY", None)

    return _build_data_source_settings_response(
        token=token,
        okx_api_key=okx_key,
        okx_secret_key=okx_secret,
        okx_passphrase=okx_pass,
        twelvedata_api_key=td_key,
        finnhub_api_key=fh_key,
        tiingo_api_key=ti_key,
    )

# ------------------------------------------------------------------------
# Skill settings
# ------------------------------------------------------------------------

@router.get("/settings/skills")
async def get_skill_settings(auth: dict = Security(_require_auth)):
    user_id = int(auth["user_id"])
    from src.agent.skills import SkillsLoader
    disabled = set(_read_skill_config(user_id).get("disabled_skills", []))
    loader = SkillsLoader(user_id=user_id, disabled_skills=disabled)
    skills_data = []
    for s in loader.skills:
        skills_data.append({
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "enabled": s.name not in disabled,
            "source": s.source,
        })
    return {"skills": skills_data, "total": len(skills_data),
            "enabled_count": sum(1 for s in skills_data if s["enabled"])}

@router.put("/settings/skills")
async def update_skill_settings(payload: dict, auth: dict = Security(_require_auth)):
    user_id = int(auth["user_id"])
    _write_skill_config(user_id, {"disabled_skills": payload.get("disabled_skills", [])})
    return {"ok": True}

@router.post("/settings/skills/import")
async def import_skill(file: UploadFile, auth: dict = Security(_require_auth)):
    user_id = int(auth["user_id"])
    import zipfile, tempfile
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "upload.zip"
            zip_path.write_bytes(await file.read())
            with zipfile.ZipFile(zip_path) as zf:
                members = [n for n in zf.namelist() if not n.startswith("__MACOSX") and not n.endswith("/")]
                if not any("SKILL.md" in m for m in members):
                    raise HTTPException(status_code=400, detail="ZIP must contain SKILL.md")
                usd = Path.home() / ".AStockPursue" / "skills" / str(user_id)
                # Find skill name from SKILL.md
                skill_name = None
                for m in members:
                    if m.endswith("SKILL.md"):
                        zf.extract(m, tmp)
                        from src.agent.frontmatter import parse_frontmatter
                        meta, _ = parse_frontmatter((Path(tmp) / m).read_text(encoding="utf-8"))
                        skill_name = meta.get("name") or Path(m).parent.name
                        break
                if not skill_name:
                    raise HTTPException(status_code=400, detail="SKILL.md must have a 'name' in frontmatter")
                dest = usd / skill_name
                dest.mkdir(parents=True, exist_ok=True)
                for m in members:
                    zf.extract(m, str(dest))
                return {"ok": True, "name": skill_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")

@router.delete("/settings/skills/{name}")
async def delete_user_skill(name: str, auth: dict = Security(_require_auth)):
    user_id = int(auth["user_id"])
    usd = Path.home() / ".AStockPursue" / "skills" / str(user_id)
    target = usd / name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Skill not found")
    import shutil
    shutil.rmtree(target)
    return {"ok": True}

# ------------------------------------------------------------------------
# MCP settings
# ------------------------------------------------------------------------

@router.get("/settings/mcp")
async def get_mcp_settings(auth: dict = Security(_require_auth)):
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    import os as _os
    config_path = Path.home() / ".AStockPursue" / "mcp_config.json"
    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except Exception:
            pass
    return {
        "service_name": "AStockPursue",
        "transport": config.get("transport", "stdio"),
        "sse_port": config.get("sse_port", 8900),
        "shell_tools_enabled": _os.getenv("ASTOCKPURSUE_ENABLE_SHELL_TOOLS", "") in ("1", "true"),
        "config_path": str(config_path),
        "install_cmd": f"python {Path(__file__).resolve().parent / 'mcp_server.py'}",
    }

@router.put("/settings/mcp")
async def update_mcp_settings(payload: dict, auth: dict = Security(_require_auth)):
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    config_path = Path.home() / ".AStockPursue" / "mcp_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2))
    os.chmod(config_path, 0o600)
    if "shell_tools_enabled" in payload:
        os.environ["ASTOCKPURSUE_ENABLE_SHELL_TOOLS"] = "1" if payload["shell_tools_enabled"] else "0"
    return {"ok": True}

