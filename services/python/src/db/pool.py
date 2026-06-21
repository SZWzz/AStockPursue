"""PostgreSQL connection pool with automatic migration.

Lazily initialised ThreadedConnectionPool.  Reads encrypted credentials from
environment variables and decrypts in memory — the plain-text password never
touches disk or logs.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.db.crypto import decrypt_password

logger = logging.getLogger(__name__)

# ── Connection pool state ───────────────────────────────────────────────────

_pool: Any = None
_pool_lock = threading.Lock()
_pool_initialised = False
_migrations_applied = False

_DEFAULT_MIN = 2
_DEFAULT_MAX = 10
_DEFAULT_ACQUIRE_TIMEOUT = 10.0
_DEFAULT_HEALTH_CHECK = True

_MIGRATIONS_PATH = Path(__file__).resolve().parents[2] / "migrations" / "init.sql"


# ── Public API ──────────────────────────────────────────────────────────────


def _build_database_url() -> str:
    """Build DATABASE_URL from individual env vars with decrypted password."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5433")
    dbname = os.getenv("DB_NAME", "stock-data")
    user = os.getenv("DB_USER", "postgres")

    enc = os.getenv("DB_PASSWORD_ENC", "")
    key = os.getenv("DB_ENCRYPTION_KEY", "")

    if enc and key:
        try:
            password = decrypt_password(enc, key)
        except Exception as e:
            logger.error("Failed to decrypt DB password: %s", e)
            password = ""
    else:
        password = os.getenv("DB_PASSWORD", "")

    if not password:
        raise RuntimeError(
            "DB password not configured. Set DB_PASSWORD_ENC + DB_ENCRYPTION_KEY, "
            "or run 'AStockPursue db-setup' to configure interactively."
        )

    raw = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    # Redact password for logging
    safe = f"postgresql://{user}:***@{host}:{port}/{dbname}"
    logger.info("Database URL: %s", safe)
    return raw


def init_pool() -> None:
    """Initialise the global connection pool (idempotent, thread-safe)."""
    global _pool, _pool_initialised
    if _pool_initialised:
        return

    with _pool_lock:
        if _pool_initialised:
            return

        try:
            import psycopg2  # noqa: F401 — availability check
            from psycopg2 import pool as pg_pool
            import psycopg2.sql  # noqa: F401 — availability check
        except ImportError:
            raise RuntimeError(
                "psycopg2-binary is required for PostgreSQL. "
                "Install it with: pip install psycopg2-binary"
            )

        database_url = _build_database_url()
        minconn = int(os.getenv("DB_POOL_MIN", str(_DEFAULT_MIN)))
        maxconn = int(os.getenv("DB_POOL_MAX", str(_DEFAULT_MAX)))

        _pool = pg_pool.ThreadedConnectionPool(
            minconn,
            maxconn,
            database_url,
            options="-c timezone=UTC",
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
            connect_timeout=10,
        )
        _pool_initialised = True
        logger.info("PG pool initialised (min=%d, max=%d)", minconn, maxconn)


def close_pool() -> None:
    """Close the connection pool (for graceful shutdown)."""
    global _pool, _pool_initialised
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
        _pool_initialised = False


@contextmanager
def get_connection():
    """Context manager: acquire a connection from the pool and return it on exit.

    Usage::

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    """
    init_pool()
    acquire_timeout = float(os.getenv("DB_POOL_ACQUIRE_TIMEOUT", str(_DEFAULT_ACQUIRE_TIMEOUT)))
    deadline = time.monotonic() + acquire_timeout
    conn = None
    last_err = None

    while time.monotonic() < deadline:
        try:
            conn = _pool.getconn()
            break
        except Exception as e:
            last_err = e
            time.sleep(0.5)

    if conn is None:
        raise RuntimeError(
            f"Failed to acquire PG connection within {acquire_timeout}s: {last_err}"
        )

    # Health check
    if os.getenv("DB_POOL_HEALTH_CHECK", str(_DEFAULT_HEALTH_CHECK)).lower() in ("1", "true", "yes"):
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except Exception:
            _pool.putconn(conn, close=True)
            raise

    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        _pool.putconn(conn, close=conn.closed != 0)


# ── Migration ───────────────────────────────────────────────────────────────


def _ensure_admin_user() -> None:
    """Create default admin user if no users exist.

    If ``ADMIN_PASSWORD`` is not set in the environment, a random 16-character
    password is generated and printed to the console.  The hardcoded default
    ``"admin123"`` is NEVER used in production — it only exists as a fallback
    for CI/test environments where ``ADMIN_PASSWORD`` is explicitly set to it.
    """
    try:
        from src.auth.jwt import hash_password

        admin_user = os.getenv("ADMIN_USER", "admin")
        admin_pass = os.getenv("ADMIN_PASSWORD", "")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@AStockPursue.local")

        # Generate a strong random password when none is configured
        if not admin_pass:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits
            admin_pass = "".join(secrets.choice(alphabet) for _ in range(16))
            logger.warning(
                "ADMIN_PASSWORD not set — generated random password. "
                "Set ADMIN_PASSWORD in .env to use a custom one."
            )
            # Also print to stdout so it's visible in docker logs
            print(f"\n{'='*60}")
            print(f"  Admin user: {admin_user}")
            print(f"  Password:   {admin_pass}")
            print("  Set ADMIN_PASSWORD in .env to change.")
            print(f"{'='*60}\n")

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM vt_users WHERE role='admin' LIMIT 1")
                if cur.fetchone():
                    return
                cur.execute(
                    "INSERT INTO vt_users (username, password_hash, email, role) VALUES (%s, %s, %s, %s)",
                    (admin_user, hash_password(admin_pass), admin_email, "admin"),
                )
            logger.info("Admin user created: %s", admin_user)
    except Exception as e:
        logger.warning("Failed to create admin user: %s", e)


_PAPER_TRADING_MIGRATION_PATH = _MIGRATIONS_PATH.parent / "002_paper_trading.sql"
_TRADING_MIGRATION_PATH = _MIGRATIONS_PATH.parent / "004_trading_orders.sql"
_paper_migration_applied = False
_trading_migration_applied = False


def init_database() -> None:
    """Execute migrations/init.sql and seed admin user (idempotent)."""
    global _migrations_applied
    if _migrations_applied:
        return

    skip = os.getenv("SKIP_AUTO_MIGRATE", "").lower() in ("1", "true", "yes")
    if skip:
        logger.info("Auto-migration skipped (SKIP_AUTO_MIGRATE=true)")
        return

    if not _MIGRATIONS_PATH.exists():
        logger.warning("Migration file not found: %s", _MIGRATIONS_PATH)
        return

    init_pool()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                sql_text = _MIGRATIONS_PATH.read_text(encoding="utf-8")
                cur.execute(sql_text)
                # Apply incremental migrations
                mig_dir = _MIGRATIONS_PATH.parent
                for mig in sorted(mig_dir.glob("*.sql")):
                    if mig.name == "init.sql":
                        continue
                    cur.execute(mig.read_text(encoding="utf-8"))
                    logger.info("Applied migration: %s", mig.name)
            logger.info("Database migration completed")
            _migrations_applied = True

        _ensure_admin_user()
    except Exception as e:
        logger.error("Database migration failed: %s", e)
        raise


def run_paper_trading_migration() -> None:
    """Execute paper-trading migration (idempotent, safe to call repeatedly)."""
    global _paper_migration_applied
    if _paper_migration_applied:
        return

    skip = os.getenv("SKIP_AUTO_MIGRATE", "").lower() in ("1", "true", "yes")
    if skip:
        return

    if not _PAPER_TRADING_MIGRATION_PATH.exists():
        logger.warning("Paper trading migration not found: %s", _PAPER_TRADING_MIGRATION_PATH)
        return

    init_pool()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                sql_text = _PAPER_TRADING_MIGRATION_PATH.read_text(encoding="utf-8")
                cur.execute(sql_text)
            logger.info("Paper trading migration completed")
            _paper_migration_applied = True
    except Exception as e:
        logger.error("Paper trading migration failed: %s", e)
        raise


def run_trading_migration() -> None:
    """Execute trading-orders migration (idempotent, safe to call repeatedly)."""
    global _trading_migration_applied
    if _trading_migration_applied:
        return

    skip = os.getenv("SKIP_AUTO_MIGRATE", "").lower() in ("1", "true", "yes")
    if skip:
        return

    if not _TRADING_MIGRATION_PATH.exists():
        logger.warning("Trading orders migration not found: %s", _TRADING_MIGRATION_PATH)
        return

    init_pool()

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                sql_text = _TRADING_MIGRATION_PATH.read_text(encoding="utf-8")
                cur.execute(sql_text)
            logger.info("Trading orders migration completed")
            _trading_migration_applied = True
    except Exception as e:
        logger.error("Trading orders migration failed: %s", e)
        raise
