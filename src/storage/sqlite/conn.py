"""Database connection primitives and date utilities for SQLite storage."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from src.storage.sqlite.utils import (
    _date_to_str,
    _date_to_str_end,
    _date_to_timestamp,
    _date_to_timestamp_end,
    _normalize_published_at,
)

logger = logging.getLogger(__name__)

# Asyncio lock for serializing database writes from async context
_db_write_lock: asyncio.Lock | None = None

# Connection caching for reuse
_cached_connection: sqlite3.Connection | None = None
_connection_lock: threading.Lock = threading.Lock()

import platformdirs  # noqa: E402

# Cross-platform database path using platformdirs
_DB_DIR = platformdirs.user_data_dir(appname="feedship", appauthor=False)
_DB_PATH = Path(_DB_DIR) / "feedship.db"


def get_db_path() -> str:
    """Return the database file path as a string.

    Returns:
        Absolute path to the SQLite database file.
    """
    return str(_DB_PATH)


def _get_connection() -> sqlite3.Connection:
    """Get or create a cached database connection with optimized settings.

    Creates the database directory if it does not exist.
    Enables WAL journal mode, sets synchronous to NORMAL,
    busy_timeout to 5000ms, and cache_size to 4000 pages.

    Connection is cached and reused to avoid repeated PRAGMA execution.

    Returns:
        sqlite3.Connection with configured pragmas and row_factory=Row.
    """
    global _cached_connection
    if _cached_connection is not None:
        return _cached_connection

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with _connection_lock:
        if _cached_connection is not None:
            return _cached_connection
        conn = sqlite3.connect(database=str(_DB_PATH), timeout=5.0)
        conn.row_factory = sqlite3.Row

        # Performance and safety pragmas
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-4000")

        _cached_connection = conn
        return conn


def _close_connection() -> None:
    """Close the cached database connection if it exists."""
    global _cached_connection
    with _connection_lock:
        if _cached_connection is not None:
            _cached_connection.close()
            _cached_connection = None


@contextmanager
def get_db():
    """Context manager for database connections.

    Yields a cached connection. Connection is NOT closed on exit since it is reused.
    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()
    """
    conn = _get_connection()
    yield conn


def init_db() -> None:
    """Initialize the database schema.

    Creates the feeds table and articles table with appropriate indexes
    if they do not already exist.

    Feeds table stores feed sources with metadata for conditional fetching.
    Articles table stores individual items with foreign key to feeds.
    """
    from src.storage.sqlite.init import DatabaseInitializer

    DatabaseInitializer().init_db()


def _get_db_write_lock() -> asyncio.Lock:
    """Get or create the singleton asyncio.Lock for serializing DB writes."""
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock
