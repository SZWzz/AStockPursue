"""Auth and admin HTTP routes."""

from __future__ import annotations

import json as _json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from pydantic import BaseModel, Field

from src.api.common import safe_error
from src.auth.rate_limit import check_rate_limit


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")
    email: str | None = None


def create_router(require_auth) -> APIRouter:
    router = APIRouter()

    # ========================================================================
    # Public auth routes (no authentication required)
    # ========================================================================

    @router.post("/api/auth/login", dependencies=[Depends(check_rate_limit)])
    async def login(request: LoginRequest):
        """Login and get a JWT token."""
        from src.auth.jwt import create_token, verify_password
        from src.db.pool import get_connection

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, username, password_hash, role, token_version FROM vt_users WHERE username = %s",
                        (request.username,),
                    )
                    row = cur.fetchone()
                    if not row or not verify_password(request.password, row[2]):
                        raise HTTPException(status_code=401, detail="Invalid username or password")

                    user_id, username, _, role, token_version = row
                    token = create_token(user_id, username, role, token_version)
                    return {"token": token, "user_id": user_id, "username": username, "role": role}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.post("/api/auth/register", dependencies=[Depends(check_rate_limit)])
    async def register(request: RegisterRequest):
        """Register a new user."""
        from src.auth.jwt import hash_password
        from src.db.pool import get_connection

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM vt_users WHERE username = %s", (request.username,))
                    if cur.fetchone():
                        raise HTTPException(status_code=409, detail="Username already exists")
                    cur.execute(
                        "INSERT INTO vt_users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING id",
                        (request.username, hash_password(request.password), request.email or ""),
                    )
                    user_id = cur.fetchone()[0]
            return {"user_id": user_id, "username": request.username}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    # ========================================================================
    # Authenticated auth routes
    # ========================================================================

    @router.post("/api/auth/change-password")
    async def change_password(request: Request, auth: dict = Security(require_auth)):
        """Change current user's password."""
        user_id = auth["user_id"]
        try:
            body = await request.json()
            old_pw = body.get("old_password", "")
            new_pw = body.get("new_password", "")
            if len(new_pw) < 4:
                raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
            from src.db.pool import get_connection
            from src.auth.jwt import verify_password, hash_password
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT password_hash FROM vt_users WHERE id=%s", (user_id,))
                    row = cur.fetchone()
                    if not row or not verify_password(old_pw, row[0]):
                        raise HTTPException(status_code=401, detail="Current password is incorrect")
                    cur.execute("UPDATE vt_users SET password_hash=%s, token_version=token_version+1, updated_at=now() WHERE id=%s",
                               (hash_password(new_pw), user_id))
            return {"ok": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.post("/api/auth/change-username")
    async def change_username(request: Request, auth: dict = Security(require_auth)):
        """Change current user's username."""
        user_id = auth["user_id"]
        try:
            body = await request.json()
            new_username = body.get("username", "").strip()
            if len(new_username) < 2:
                raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
            from src.db.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM vt_users WHERE username=%s AND id!=%s", (new_username, user_id))
                    if cur.fetchone():
                        raise HTTPException(status_code=409, detail="Username already taken")
                    cur.execute("UPDATE vt_users SET username=%s, updated_at=now() WHERE id=%s", (new_username, user_id))
            return {"ok": True, "username": new_username}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.get("/api/auth/me")
    async def get_current_user(auth: dict = Security(require_auth)):
        """Get current user info from JWT, including llm_config."""
        user_id = auth["user_id"]
        try:
            from src.db.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, username, role, email, llm_config FROM vt_users WHERE id=%s", (user_id,))
                    row = cur.fetchone()
                    if row:
                        return {
                            "user_id": row[0], "username": row[1], "role": row[2],
                            "email": row[3] or "",
                            "llm_config": row[4] if isinstance(row[4], dict) else {},
                        }
        except Exception:
            pass
        return auth

    @router.post("/api/auth/llm-config")
    async def save_user_llm_config(
        request: Request,
        auth: dict = Security(require_auth),
    ):
        """Save per-user LLM configuration (encrypted API key)."""
        user_id = auth["user_id"]
        try:
            body = await request.json()
            from src.db.pool import get_connection
            from src.auth.user_config import encrypt_config, _SENSITIVE_LLM_FIELDS
            import json as _json
            body = encrypt_config(body, _SENSITIVE_LLM_FIELDS)
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE vt_users SET llm_config=%s, updated_at=now() WHERE id=%s",
                        (_json.dumps(body, ensure_ascii=False), user_id),
                    )
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    @router.get("/api/auth/llm-config")
    async def get_user_llm_config(auth: dict = Security(require_auth)):
        """Get current user's LLM configuration (decrypted fields)."""
        user_id = auth["user_id"]
        try:
            from src.db.pool import get_connection
            from src.auth.user_config import decrypt_config, _SENSITIVE_LLM_FIELDS
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT llm_config FROM vt_users WHERE id=%s", (user_id,))
                    row = cur.fetchone()
                    if row:
                        cfg = row[0] if isinstance(row[0], dict) else {}
                        cfg = decrypt_config(cfg, _SENSITIVE_LLM_FIELDS)
                        return {"llm_config": cfg}
        except Exception:
            pass
        return {"llm_config": {}}

    @router.get("/api/auth/data-source-config")
    async def get_user_data_source_config(auth: dict = Security(require_auth)):
        """Get current user's data source configuration (decrypted fields)."""
        user_id = auth["user_id"]
        try:
            from src.db.pool import get_connection
            from src.auth.user_config import decrypt_config, _SENSITIVE_DS_FIELDS
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT data_source_config FROM vt_users WHERE id=%s", (user_id,))
                    row = cur.fetchone()
                    if row:
                        cfg = row[0] if isinstance(row[0], dict) else {}
                        cfg = decrypt_config(cfg, _SENSITIVE_DS_FIELDS)
                        return {"data_source_config": cfg}
        except Exception:
            pass
        return {"data_source_config": {}}

    @router.post("/api/auth/data-source-config")
    async def save_user_data_source_config(
        request: Request,
        auth: dict = Security(require_auth),
    ):
        """Save per-user data source configuration (encrypted tokens)."""
        user_id = auth["user_id"]
        try:
            body = await request.json()
            from src.db.pool import get_connection
            from src.auth.user_config import encrypt_config, _SENSITIVE_DS_FIELDS
            import json as _json
            body = encrypt_config(body, _SENSITIVE_DS_FIELDS)
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE vt_users SET data_source_config=%s, updated_at=now() WHERE id=%s",
                        (_json.dumps(body, ensure_ascii=False), user_id),
                    )
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    # ========================================================================
    # Admin routes
    # ========================================================================

    @router.get("/admin/users")
    async def list_users(auth: dict = Security(require_auth)):
        """List all users (admin only)."""
        if auth.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin only")
        try:
            from src.db.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, username, email, role, created_at, "
                        "llm_config->>'provider' as llm_provider, llm_config->>'model' as llm_model, "
                        "CASE WHEN data_source_config->>'tushare_token' IS NOT NULL AND data_source_config->>'tushare_token' != '' THEN true ELSE false END as tushare_configured "
                        "FROM vt_users ORDER BY id"
                    )
                    return {"users": [
                        {"id": r[0], "username": r[1], "email": r[2] or "", "role": r[3],
                         "created_at": str(r[4]), "llm_provider": r[5] or "", "llm_model": r[6] or "",
                         "tushare_configured": bool(r[7]) if len(r) > 7 else False}
                        for r in cur.fetchall()
                    ]}
        except Exception as e:
            return {"users": [], "error": str(e)}

    @router.delete("/admin/users/{user_id}")
    async def delete_user(user_id: int, auth: dict = Security(require_auth)):
        """Delete a user (admin only)."""
        if auth.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin only")
        try:
            from src.db.pool import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM vt_users WHERE id=%s", (user_id,))
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=safe_error(e))

    # ========================================================================
    # SSE token endpoint (short-lived JWT for EventSource query param)
    # ========================================================================

    @router.get("/api/sse-token", dependencies=[Depends(require_auth)])
    async def get_sse_token(auth: dict = Security(require_auth)):
        """Issue a short-lived JWT (5 min) for SSE query-param auth.

        SSE (EventSource) cannot set custom HTTP headers, so the JWT must
        be passed as a query parameter. This short-lived token limits the
        damage window if the token appears in server/proxy logs.
        """
        from src.auth.jwt import create_sse_token
        token = create_sse_token(
            user_id=auth["user_id"],
            username=auth.get("username", ""),
        )
        return {"token": token, "expires_in_minutes": 5}

    return router
