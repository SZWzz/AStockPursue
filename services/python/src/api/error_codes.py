"""Standardised API error codes and helper for consistent error responses.

Usage::

    from src.api.error_codes import api_error

    raise api_error(ErrorCode.NOT_FOUND, "Workflow not found")
    raise api_error(ErrorCode.VALIDATION_ERROR, "Name is required", status_code=422)
"""

from __future__ import annotations

from enum import Enum

from fastapi import HTTPException


class ErrorCode(str, Enum):
    """Machine-readable error codes for client-side handling."""

    # 400 — Bad Request
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"

    # 401 — Unauthorized
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_TOKEN = "INVALID_TOKEN"

    # 403 — Forbidden
    FORBIDDEN = "FORBIDDEN"

    # 404 — Not Found
    NOT_FOUND = "NOT_FOUND"
    WORKFLOW_NOT_FOUND = "WORKFLOW_NOT_FOUND"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"

    # 409 — Conflict
    CONFLICT = "CONFLICT"
    ALREADY_RUNNING = "ALREADY_RUNNING"
    WORKFLOW_LOCKED = "WORKFLOW_LOCKED"

    # 422 — Unprocessable Entity
    UNPROCESSABLE = "UNPROCESSABLE"

    # 500 — Internal Server Error
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # 501 — Not Implemented
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


# Map ErrorCode → default HTTP status
_ERROR_CODE_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.INVALID_INPUT: 400,
    ErrorCode.MISSING_FIELD: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.WORKFLOW_NOT_FOUND: 404,
    ErrorCode.PROJECT_NOT_FOUND: 404,
    ErrorCode.RUN_NOT_FOUND: 404,
    ErrorCode.NODE_NOT_FOUND: 404,
    ErrorCode.TEMPLATE_NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.ALREADY_RUNNING: 409,
    ErrorCode.WORKFLOW_LOCKED: 423,
    ErrorCode.UNPROCESSABLE: 422,
    ErrorCode.INTERNAL_ERROR: 500,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.EXECUTION_ERROR: 500,
    ErrorCode.NOT_IMPLEMENTED: 501,
}


def api_error(
    code: ErrorCode,
    detail: str,
    *,
    status_code: int | None = None,
) -> HTTPException:
    """Create an HTTPException with a standardised error-code body.

    Args:
        code: Machine-readable error code from ``ErrorCode`` enum.
        detail: Human-readable error message (safe for client display).
        status_code: Override the default HTTP status for this code.

    Returns:
        ``HTTPException`` ready to raise.
    """
    status = status_code if status_code is not None else _ERROR_CODE_STATUS.get(code, 500)
    return HTTPException(
        status_code=status,
        detail={"error_code": code.value, "message": detail},
    )


def internal_error() -> HTTPException:
    """Standard 500 with a generic client-safe message."""
    return api_error(ErrorCode.INTERNAL_ERROR, "An internal error occurred")


def not_found(entity: str) -> HTTPException:
    """Standard 404 for a named entity."""
    return api_error(ErrorCode.NOT_FOUND, f"{entity} not found")
