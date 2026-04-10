"""Database connection primitives and date utilities for SQLite storage."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Asyncio lock for serializing database writes from async context
_db_write_lock: asyncio.Lock | None = None


def _get_db_write_lock() -> asyncio.Lock:
    """Get or create the singleton asyncio.Lock for serializing DB writes."""
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock


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
    """Create and return a database connection with optimized settings.

    Creates the database directory if it does not exist.
    Enables WAL journal mode, sets synchronous to NORMAL,
    busy_timeout to 5000ms, and cache_size to 4000 pages.

    Returns:
        sqlite3.Connection with configured pragmas and row_factory=Row.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(database=str(_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row

    # Performance and safety pragmas
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA cache_size=-4000")

    return conn


@contextmanager
def get_db():
    """Context manager for database connections.

    Yields a configured connection and ensures it is closed on exit.
    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            conn.commit()
    """
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database schema.

    Creates the feeds table and articles table with appropriate indexes
    if they do not already exist.

    Feeds table stores feed sources with metadata for conditional fetching.
    Articles table stores individual items with foreign key to feeds.
    """
    from src.storage.sqlite.init import DatabaseInitializer

    DatabaseInitializer().init_db()


def _normalize_published_at(published_at: str | None, tz) -> str:
    """Normalize published_at to YYYY-MM-DD HH:MM:SS format string.

    Handles RFC-2822 ("Wed, 31 Oct 2024 12:00:00 GMT") and ISO
    ("2024-10-31T12:00:00Z") formats. Falls back to current time.

    Returns:
        Formatted date string (YYYY-MM-DD HH:MM:SS) or None if published_at is None.
    """
    from datetime import datetime
    from email.utils import parsedate_to_datetime

    if not published_at:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        # Try RFC-2822 first (feedparser standard)
        dt = parsedate_to_datetime(published_at)
        dt = dt.astimezone(tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        pass

    try:
        # Try ISO format
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        dt = dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        pass

    # Fallback: try YYYY-MM-DD direct
    if len(published_at) >= 10 and published_at[4:5] == "-":
        dt = datetime.strptime(published_at[:10], "%Y-%m-%d").replace(tzinfo=tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    return time.strftime("%Y-%m-%d %H:%M:%S")


def _date_to_timestamp(date_str: str, tz) -> int:
    """Convert YYYY-MM-DD to Unix timestamp at start of day in timezone."""
    from datetime import datetime

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=tz)
    return int(dt.timestamp())


def _date_to_timestamp_end(date_str: str, tz) -> int:
    """Convert YYYY-MM-DD to Unix timestamp at end of day (23:59:59) in timezone."""
    from datetime import datetime

    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())


def _date_to_str(date_str: str, tz) -> str:
    """Convert YYYY-MM-DD to YYYY-MM-DD HH:MM:SS string at start of day in timezone.

    Note: tz is ignored but kept for API compatibility with _date_to_timestamp.
    The conversion uses the timezone to determine the actual start moment.
    """
    from datetime import datetime

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _date_to_str_end(date_str: str, tz) -> str:
    """Convert YYYY-MM-DD to YYYY-MM-DD HH:MM:SS string at end of day (23:59:59) in timezone.

    Note: tz is ignored but kept for API compatibility with _date_to_timestamp_end.
    """
    from datetime import datetime

    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    dt = dt.replace(hour=23, minute=59, second=59)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
