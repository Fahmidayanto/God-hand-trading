"""
Neon PostgreSQL Database Connection Manager.

Provides a connection pool using psycopg2 for the Track 1 real-time pipeline.
All Track 1 writes (OHLCV, structures, trades, agent decisions) use this pool.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2 import pool as pg_pool

logger = logging.getLogger(__name__)

# Global connection pool (initialized lazily)
_pool: Optional[pg_pool.ThreadedConnectionPool] = None


def _build_dsn() -> dict:
    """
    Build DSN kwargs from application settings.

    Uses pydantic_settings (which already loaded .env) so that
    credentials are always available regardless of os.getenv state.
    """
    from app.config import get_settings
    s = get_settings()
    return {
        "host":             s.PGHOST or None,
        "dbname":           s.PGDATABASE or None,
        "user":             s.PGUSER or None,
        "password":         s.PGPASSWORD or None,
        "sslmode":          s.PGSSLMODE or "require",
        "connect_timeout":  10,
        "application_name": "valuecell_track1",
    }


def init_db_pool(minconn: int = 1, maxconn: int = 5) -> bool:
    """
    Initialize the psycopg2 threaded connection pool.

    Called once at FastAPI lifespan startup. Safe to call multiple times
    (no-op if pool is already initialized).

    Args:
        minconn: Minimum idle connections to keep open.
        maxconn: Maximum connections in the pool.

    Returns:
        True if pool was successfully created/already exists.
    """
    global _pool

    if _pool is not None:
        return True

    dsn = _build_dsn()
    missing = [k for k, v in dsn.items() if v is None and k in ("host", "dbname", "user", "password")]
    if missing:
        logger.error(f"[DB] Missing environment variables: {missing}. Neon DB pool NOT initialized.")
        return False

    try:
        _pool = pg_pool.ThreadedConnectionPool(minconn, maxconn, **dsn)
        logger.info(
            f"[DB] [OK] Neon PostgreSQL pool initialized "
            f"(min={minconn}, max={maxconn}, host={dsn['host']})"
        )
        return True
    except Exception as exc:
        logger.error(f"[DB] [ERROR] Failed to create connection pool: {exc}")
        _pool = None
        return False


def close_db_pool() -> None:
    """
    Close all connections in the pool.

    Called at FastAPI lifespan shutdown.
    """
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
            logger.info("[DB] Connection pool closed.")
        except Exception as exc:
            logger.warning(f"[DB] Error closing pool: {exc}")
        finally:
            _pool = None


def is_pool_ready() -> bool:
    """Return True if the connection pool is initialized."""
    return _pool is not None


@contextmanager
def get_db_conn() -> Generator:
    """
    Context manager that yields a psycopg2 connection from the pool.

    Usage::

        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
            conn.commit()

    The connection is automatically returned to the pool after the block.
    On exception, the transaction is rolled back before returning.
    """
    if _pool is None:
        raise RuntimeError("[DB] Connection pool is not initialized. Call init_db_pool() first.")

    conn = _pool.getconn()
    is_broken = False
    try:
        # Check if the connection has been closed or went dead while sitting idle in pool
        connection_dead = False
        if conn.closed != 0:
            connection_dead = True
        else:
            try:
                with conn.cursor() as test_cur:
                    test_cur.execute("SELECT 1")
            except Exception:
                connection_dead = True

        if connection_dead:
            is_broken = True
            # Discard the closed connection and request a new one
            _pool.putconn(conn, close=True)
            conn = _pool.getconn()
            is_broken = False  # Reset flag for the new connection
        yield conn
    except Exception:
        is_broken = True
        try:
            if conn.closed == 0:
                conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            if is_broken or conn.closed != 0:
                _pool.putconn(conn, close=True)
            else:
                _pool.putconn(conn)
        except Exception as put_exc:
            logger.warning(f"[DB] Error returning connection to pool: {put_exc}")


def test_connection() -> bool:
    """
    Quick connectivity test — executes SELECT 1.

    Returns:
        True if the database is reachable.
    """
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        logger.info("[DB] [OK] Connection test passed.")
        return True
    except Exception as exc:
        logger.error(f"[DB] [ERROR] Connection test failed: {exc}")
        return False
