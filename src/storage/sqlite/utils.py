"""Shared utility functions for SQLite storage."""

from __future__ import annotations

import time


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
