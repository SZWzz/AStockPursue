"""Tests for src.db.pool — PostgreSQL connection pool management."""

from __future__ import annotations

import sys
import threading
from unittest.mock import MagicMock, patch

import pytest


def _mock_psycopg2_modules():
    """Pre-register mock psycopg2 modules so init_pool() imports succeed."""
    mock_pg = MagicMock()
    mock_pg_pool = MagicMock()
    mock_pg_sql = MagicMock()
    mock_pg.extras = MagicMock()
    return {
        "psycopg2": mock_pg,
        "psycopg2.pool": mock_pg_pool,
        "psycopg2.sql": mock_pg_sql,
        "psycopg2.extras": mock_pg.extras,
    }


@pytest.mark.unit
class TestBuildDatabaseUrl:
    def test_build_database_url_with_all_env_vars(self, monkeypatch):
        """Verify _build_database_url constructs the correct DSN from env vars."""
        monkeypatch.setenv("DB_HOST", "db.example.com")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "mydb")
        monkeypatch.setenv("DB_USER", "appuser")
        monkeypatch.setenv("DB_PASSWORD", "plainpass")

        from src.db.pool import _build_database_url

        url = _build_database_url()
        assert url == "postgresql://appuser:plainpass@db.example.com:5432/mydb"

    def test_build_database_url_default_values(self, monkeypatch):
        """Verify defaults for missing env vars."""
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        # Don't set DB_HOST, DB_PORT, DB_NAME, DB_USER

        from src.db.pool import _build_database_url

        url = _build_database_url()
        assert "localhost" in url
        assert "5433" in url
        assert "stock-data" in url
        assert "postgres" in url

    def test_build_database_url_with_encrypted_password(self, monkeypatch):
        """Verify encrypted password is decrypted when DB_PASSWORD_ENC + DB_ENCRYPTION_KEY are set."""
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        monkeypatch.setenv("DB_NAME", "testdb")
        monkeypatch.setenv("DB_USER", "admin")
        monkeypatch.setenv("DB_PASSWORD_ENC", "encrypted_value")
        monkeypatch.setenv("DB_ENCRYPTION_KEY", "test_key_base64")

        with patch("src.db.pool.decrypt_password", return_value="decrypted_pass") as mock_decrypt:
            from src.db.pool import _build_database_url

            url = _build_database_url()
            assert "decrypted_pass" in url
            mock_decrypt.assert_called_once_with("encrypted_value", "test_key_base64")

    def test_build_database_url_no_password_raises(self, monkeypatch):
        """Verify RuntimeError when no password is configured."""
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        monkeypatch.delenv("DB_PASSWORD_ENC", raising=False)
        monkeypatch.delenv("DB_ENCRYPTION_KEY", raising=False)

        from src.db.pool import _build_database_url

        with pytest.raises(RuntimeError, match="password not configured"):
            _build_database_url()


@pytest.mark.unit
class TestInitPool:
    def test_init_pool_creates_pool_with_env_config(self, monkeypatch):
        """Verify init_pool creates a ThreadedConnectionPool with min/max from env."""
        _reset_pool_state()

        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_POOL_MIN", "3")
        monkeypatch.setenv("DB_POOL_MAX", "15")

        mock_tcp = MagicMock()

        with patch.dict(sys.modules, _mock_psycopg2_modules()), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_tcp):
            from src.db.pool import init_pool

            init_pool()
            import psycopg2.pool as pg_pool

            pg_pool.ThreadedConnectionPool.assert_called_once()
            args, kwargs = pg_pool.ThreadedConnectionPool.call_args
            assert args[0] == 3  # minconn
            assert args[1] == 15  # maxconn

    def test_init_pool_idempotent(self, monkeypatch):
        """Verify init_pool is idempotent — only creates pool once."""
        _reset_pool_state()

        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        with patch.dict(sys.modules, _mock_psycopg2_modules()), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=MagicMock()):
            from src.db.pool import init_pool

            init_pool()
            init_pool()  # second call should be no-op
            # Should only be called once
            import psycopg2.pool as pg_pool

            assert pg_pool.ThreadedConnectionPool.call_count == 1

    def test_init_pool_thread_safety(self, monkeypatch):
        """Verify concurrent init_pool calls only create one pool."""
        _reset_pool_state()

        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        results = []
        barrier = threading.Barrier(5)
        exc_holder = []

        def _init():
            try:
                barrier.wait()
                from src.db.pool import init_pool
                init_pool()
                from src.db.pool import _pool
                results.append(_pool)
            except Exception as e:
                exc_holder.append(e)

        with patch.dict(sys.modules, _mock_psycopg2_modules()), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=MagicMock()):
            threads = [threading.Thread(target=_init) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not exc_holder
        # All results should point to the same pool object
        first = results[0]
        for r in results[1:]:
            assert r is first

    def test_init_pool_with_default_minmax(self, monkeypatch):
        """Verify default min/max values when env vars are not set."""
        _reset_pool_state()

        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        with patch.dict(sys.modules, _mock_psycopg2_modules()), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=MagicMock()):
            from src.db.pool import init_pool

            init_pool()
            import psycopg2.pool as pg_pool

            args, _ = pg_pool.ThreadedConnectionPool.call_args
            assert args[0] == 2  # default min
            assert args[1] == 10  # default max


@pytest.mark.unit
class TestClosePool:
    def test_close_pool_sets_pool_to_none(self):
        """Verify close_pool sets _pool to None."""
        _reset_pool_state()
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        import src.db.pool as mod

        with patch.dict(sys.modules, _mock_psycopg2_modules()), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=MagicMock()):
            mod.init_pool()
            assert mod._pool is not None
            mod.close_pool()
            assert mod._pool is None

        monkeypatch.undo()


@pytest.mark.unit
class TestGetConnection:
    def test_get_connection_yields_and_returns(self, monkeypatch):
        """Verify get_connection context manager acquires and releases a connection."""
        _reset_pool_state()

        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PASSWORD", "testpass")

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn

        with patch.dict(sys.modules, _mock_psycopg2_modules()), \
             patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool):
            import src.db.pool as mod
            from src.db.pool import get_connection, _acquire_with_retry

            with get_connection() as conn:
                assert conn is not None

            # After context exit, putconn should be called on the pool
            assert mod._pool.putconn.called


@pytest.mark.unit
class TestAcquireWithRetry:
    def test_acquire_with_retry_retries_on_exhaustion(self):
        """Verify _acquire_with_retry retries when pool is exhausted."""
        mock_pool = MagicMock()
        # First two calls raise, third succeeds
        mock_pool.getconn.side_effect = [
            Exception("pool exhausted"),
            Exception("pool exhausted"),
            MagicMock(),
        ]

        from src.db.pool import _acquire_with_retry

        conn = _acquire_with_retry(mock_pool)
        assert conn is not None
        assert mock_pool.getconn.call_count == 3

    def test_acquire_with_retry_raises_after_timeout(self, monkeypatch):
        """Verify _acquire_with_retry raises after timeout."""
        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = Exception("pool exhausted")

        # Make the deadline immediate so we don't actually wait
        monkeypatch.setenv("DB_POOL_ACQUIRE_TIMEOUT", "0.1")
        monkeypatch.setenv("DB_POOL_HEALTH_CHECK", "false")

        from src.db.pool import _acquire_with_retry

        with pytest.raises(RuntimeError, match="Failed to acquire"):
            _acquire_with_retry(mock_pool)


@pytest.mark.unit
class TestInitDatabase:
    def test_init_database_skips_when_skip_auto_migrate_set(self, monkeypatch):
        """Verify init_database returns early when SKIP_AUTO_MIGRATE is set."""
        _reset_migrations()

        monkeypatch.setenv("SKIP_AUTO_MIGRATE", "true")

        from src.db.pool import init_database

        init_database()
        from src.db.pool import _migrations_applied

        assert not _migrations_applied


@pytest.mark.unit
class TestEnsureAdminUser:
    def test_ensure_admin_user_creates_admin_when_not_exists(self, monkeypatch):
        """Verify _ensure_admin_user creates admin user when none exists."""
        monkeypatch.setenv("ADMIN_PASSWORD", "admin123")

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No existing admin
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        from contextlib import contextmanager

        @contextmanager
        def _mock_conn_ctx():
            yield mock_conn

        with patch("src.db.pool.get_connection", side_effect=_mock_conn_ctx), \
             patch("src.auth.jwt.hash_password", return_value="hashed_pw"):
            from src.db.pool import _ensure_admin_user

            _ensure_admin_user()
            assert mock_cursor.execute.called, "Expected cursor.execute to be called for INSERT"


# ── Helpers ────────────────────────────────────────────────────────────────


def _reset_pool_state():
    """Reset module-level pool state between tests."""
    import src.db.pool as mod

    mod._pool = None
    mod._pool_initialised = False


def _reset_migrations():
    """Reset module-level migration state between tests."""
    import src.db.pool as mod

    mod._migrations_applied = False
