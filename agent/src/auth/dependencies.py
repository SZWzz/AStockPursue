"""FastAPI auth dependencies — JWT + API_AUTH_KEY fallback."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.jwt import verify_token

_security = HTTPBearer(auto_error=False)


def _load_data_source_tokens(user_id: int) -> None:
    """Set per-user data-source tokens (TUSHARE_TOKEN, etc.) into os.environ."""
    try:
        from src.auth.user_config import load_user_config
        load_user_config(user_id)
    except Exception:
        pass


async def require_auth(
    request: Request,
    cred: Optional[HTTPAuthorizationCredentials] = Security(_security),
    jwt: Optional[str] = Query(None),
) -> dict:
    """Authenticate request via JWT (preferred) or API_AUTH_KEY (fallback).

    Accepts token from Authorization header or ``?jwt=`` query parameter
    (needed by SSE EventSource which cannot set custom headers).

    Returns user payload dict: {user_id, username, role, token_version}.

    Also loads per-user data-source tokens into os.environ so every
    authenticated request automatically has access to the caller's
    TUSHARE_TOKEN, OKX_API_KEY, etc.
    """
    api_key = os.getenv("API_AUTH_KEY", "")

    token = (cred.credentials if cred and cred.credentials else "") or (jwt or "")

    if token:
        # Try JWT first
        payload = verify_token(token)
        if payload:
            _load_data_source_tokens(payload.get("user_id", 1))
            return payload

        # Try API_AUTH_KEY
        if api_key and hmac.compare_digest(token, api_key):
            _load_data_source_tokens(1)
            return {"user_id": 1, "username": "admin", "role": "admin", "token_version": 0}

        raise HTTPException(status_code=401, detail="Invalid token")

    # No credentials
    if api_key:
        raise HTTPException(status_code=401, detail="Authorization required")

    # No API key configured — allow localhost only
    host = request.client.host if request.client else ""
    allowed = {"127.0.0.1", "localhost", "::1"}
    if host not in allowed:
        raise HTTPException(status_code=403, detail="Remote access requires authentication")

    _load_data_source_tokens(1)
    return {"user_id": 1, "username": "local", "role": "admin", "token_version": 0}
