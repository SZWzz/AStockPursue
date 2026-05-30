"""Session HTTP routes for the Web UI."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.auth.dependencies import require_auth as _require_auth
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.common import validate_path_param, SESSIONS_DIR, RUNS_DIR, shell_tools_enabled_for_request


class CreateSessionRequest(BaseModel):
    title: str = Field("", description="Session title")
    config: Optional[Dict[str, Any]] = Field(None, description="Session config")


class SessionResponse(BaseModel):
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    last_attempt_id: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str
    linked_attempt_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None


_session_service = None


def _get_session_service():
    global _session_service
    if _session_service is not None:
        return _session_service
    if os.getenv("ENABLE_SESSION_RUNTIME", "true").lower() != "true":
        return None
    import asyncio
    from src.session.events import EventBus
    from src.session.service import SessionService, _create_store
    store = _create_store(base_dir=SESSIONS_DIR)
    event_bus = EventBus()
    try:
        loop = asyncio.get_event_loop()
        event_bus.set_loop(loop)
    except RuntimeError:
        pass
    _session_service = SessionService(store=store, event_bus=event_bus, runs_dir=RUNS_DIR)
    return _session_service


router = APIRouter()

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest, auth: dict = Depends(_require_auth)):
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    config = request.config or {}
    config["_user_id"] = auth["user_id"]
    session = svc.create_session(title=request.title, config=config)
    return SessionResponse(
        session_id=session.session_id, title=session.title,
        status=session.status.value, created_at=session.created_at,
        updated_at=session.updated_at, last_attempt_id=session.last_attempt_id,
    )

@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(limit: int = Query(50, ge=1, le=200)):
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    sessions = svc.list_sessions(limit=limit)
    return [
        SessionResponse(
            session_id=s.session_id, title=s.title, status=s.status.value,
            created_at=s.created_at, updated_at=s.updated_at,
            last_attempt_id=s.last_attempt_id,
        )
        for s in sessions
    ]

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, auth: dict = Depends(_require_auth)):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return SessionResponse(
        session_id=session.session_id, title=session.title,
        status=session.status.value, created_at=session.created_at,
        updated_at=session.updated_at, last_attempt_id=session.last_attempt_id,
    )

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, auth: dict = Depends(_require_auth)):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    deleted = svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"status": "deleted", "session_id": session_id}

@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, req: UpdateSessionRequest):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    session = svc.store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    if req.title is not None:
        session.title = req.title
    session.updated_at = datetime.now().isoformat()
    svc.store.update_session(session)
    return {"status": "updated", "session_id": session_id}

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, payload: SendMessageRequest, http_request: Request, auth: dict = Depends(_require_auth)):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    try:
        result = await svc.send_message(
            session_id=session_id, content=payload.content,
            include_shell_tools=shell_tools_enabled_for_request(http_request),
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    cancelled = svc.cancel_current(session_id)
    if not cancelled:
        return {"status": "no_active_loop"}
    return {"status": "cancelled"}

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(session_id: str, limit: int = Query(100, ge=1, le=1000), auth: dict = Depends(_require_auth)):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    messages = svc.get_messages(session_id, limit=limit)
    return [
        MessageResponse(
            message_id=m.message_id, session_id=m.session_id, role=m.role,
            content=m.content, created_at=m.created_at,
            linked_attempt_id=m.linked_attempt_id,
            metadata=m.metadata if m.metadata else None,
        )
        for m in messages
    ]

@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, request: Request, last_event_id: Optional[str] = Query(None, alias="Last-Event-ID")):
    validate_path_param(session_id, "session_id")
    svc = _get_session_service()
    if not svc:
        raise HTTPException(status_code=501, detail="Session runtime not enabled")
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    header_id = request.headers.get("Last-Event-ID")
    event_id = header_id or last_event_id

    async def event_generator():
        async for event in svc.event_bus.subscribe(session_id, last_event_id=event_id):
            if await request.is_disconnected():
                break
            yield event.to_sse()

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )

