"""Common fixtures and helpers for db store integration tests.

Provides mock psycopg2 connections/cursors and factory functions
to patch ``get_connection`` in store modules.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Ensure psycopg2 is mock-importable so that store modules which do
# ``import psycopg2`` at module level (e.g. factor_kb_store) don't fail.
# ---------------------------------------------------------------------------

if "psycopg2" not in sys.modules:
    _mock_psycopg2 = MagicMock(name="psycopg2")
    _mock_psycopg2_extras = MagicMock(name="psycopg2.extras")
    _mock_psycopg2.extras = _mock_psycopg2_extras
    sys.modules["psycopg2"] = _mock_psycopg2
    sys.modules["psycopg2.extras"] = _mock_psycopg2_extras


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_conn():
    """Create a mock psycopg2 connection with cursor.

    Returns a (conn, cursor) tuple.  Both support context-manager
    semantics so that ``with get_connection() as conn: with conn.cursor()
    as cur:`` works without real PostgreSQL.
    """
    conn = MagicMock(name="psycopg2_connection")
    cursor = MagicMock(name="psycopg2_cursor")

    # Connection context manager (needed when factory wraps get_connection)
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)

    # Cursor context manager
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)

    conn.cursor.return_value = cursor
    return conn, cursor


# ---------------------------------------------------------------------------
# Helpers for patching get_connection
# ---------------------------------------------------------------------------

def mock_get_connection_factory(conn):
    """Return a callable suitable for replacing ``src.db.xxx.get_connection``.

    When called the returned function acts as a context manager that yields
    *conn* — exactly the shape store modules expect::

        monkeypatch.setattr(mod, "get_connection", mock_get_connection_factory(conn))
    """
    @contextmanager
    def _get():
        yield conn
    return _get
