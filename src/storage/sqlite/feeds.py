"""Feed CRUD operations for SQLite storage.

Provides functions for creating, reading, updating, and deleting feeds
in the SQLite database.
"""

from __future__ import annotations

from src.models import Feed
from src.storage.sqlite.conn import get_db


def feed_exists(url: str) -> bool:
    """Check if feed with given URL exists.

    Args:
        url: The feed URL to check.

    Returns:
        True if a feed with the given URL exists, False otherwise.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM feeds WHERE url = ?", (url,))
        return cursor.fetchone() is not None


def add_feed(feed: Feed) -> Feed:
    """Insert new feed, return Feed object.

    Args:
        feed: Feed object with all required fields.

    Returns:
        The same Feed object that was inserted.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO feeds (id, name, url, etag, modified_at, fetched_at, created_at, weight, refresh_interval)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                feed.id,
                feed.name,
                feed.url,
                feed.etag,
                feed.modified_at,
                feed.fetched_at,
                feed.created_at,
                feed.weight,
                feed.refresh_interval,
            ),
        )
        conn.commit()
        return feed


def list_feeds() -> list[Feed]:
    """List all feeds with article counts.

    Returns:
        List of Feed objects ordered by creation date descending,
        each with an articles_count attribute attached.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.name, f.url, f.etag, f.modified_at, f.fetched_at,
                   f.created_at, f.weight, f."group", f.refresh_interval,
                   COUNT(a.id) as articles_count
            FROM feeds f
            LEFT JOIN articles a ON f.id = a.feed_id
            GROUP BY f.id
            ORDER BY f.created_at DESC
            """
        )
        rows = cursor.fetchall()
        feeds = []
        for row in rows:
            feed = Feed(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                etag=row["etag"],
                modified_at=row["modified_at"],
                fetched_at=row["fetched_at"],
                created_at=row["created_at"],
                weight=row["weight"],
                group=row["group"],
                refresh_interval=row["refresh_interval"],
            )
            feed.articles_count = row["articles_count"]
            feeds.append(feed)
        return feeds


def get_feed(feed_id: str) -> Feed | None:
    """Get single feed by ID.

    Args:
        feed_id: The feed ID to look up.

    Returns:
        Feed object if found, None otherwise.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, url, etag, modified_at, fetched_at, created_at, weight, "group", refresh_interval FROM feeds WHERE id = ?',
            (feed_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Feed(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            etag=row["etag"],
            modified_at=row["modified_at"],
            fetched_at=row["fetched_at"],
            created_at=row["created_at"],
            weight=row["weight"],
            group=row["group"],
            refresh_interval=row["refresh_interval"],
        )


def get_feeds_by_ids(ids: list[str]) -> dict[str, Feed]:
    """Get feeds by IDs in batch, returning a dict mapping id -> Feed.

    Args:
        ids: List of feed IDs.

    Returns:
        Dict mapping feed ID to Feed object. Missing entries are omitted.
    """
    if not ids:
        return {}
    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(  # nosec B608
            f'SELECT id, name, url, etag, modified_at, fetched_at, created_at, weight, "group", refresh_interval FROM feeds WHERE id IN ({placeholders})',
            ids,
        )
        return {
            row["id"]: Feed(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                etag=row["etag"],
                modified_at=row["modified_at"],
                fetched_at=row["fetched_at"],
                created_at=row["created_at"],
                weight=row["weight"],
                group=row["group"],
                refresh_interval=row["refresh_interval"],
            )
            for row in cursor.fetchall()
        }


def remove_feed(feed_id: str) -> bool:
    """Delete feed by ID.

    Args:
        feed_id: The ID of the feed to delete.

    Returns:
        True if the feed was deleted, False if it was not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def upsert_feed(feed: Feed) -> tuple[Feed, bool]:
    """Insert or update a feed by URL, returning the Feed object and whether it was new.

    If a feed with the same URL exists, the existing id and created_at are preserved
    while other fields are updated. If no matching feed exists, a new one is inserted.

    Args:
        feed: Feed object with all fields to save.

    Returns:
        Tuple of (saved Feed object, is_new) where is_new is True for insert,
        False for update.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, created_at FROM feeds WHERE url = ?", (feed.url,))
        existing = cursor.fetchone()

        if existing:
            # UPDATE existing feed, preserving original id
            cursor.execute(
                """UPDATE feeds SET name = ?, etag = ?, modified_at = ?, fetched_at = ?, weight = ?, metadata = ?, "group" = ?, refresh_interval = ?
                   WHERE url = ?""",
                (
                    feed.name,
                    feed.etag,
                    feed.modified_at,
                    feed.fetched_at,
                    feed.weight,
                    feed.metadata,
                    feed.group,
                    feed.refresh_interval,
                    feed.url,
                ),
            )
            conn.commit()
            # Return Feed with preserved id
            return (
                Feed(
                    id=existing["id"],
                    name=feed.name,
                    url=feed.url,
                    etag=feed.etag,
                    modified_at=feed.modified_at,
                    fetched_at=feed.fetched_at,
                    created_at=existing["created_at"],
                    weight=feed.weight,
                    metadata=feed.metadata,
                    group=feed.group,
                    refresh_interval=feed.refresh_interval,
                ),
                False,  # not new
            )
        else:
            # INSERT new feed
            cursor.execute(
                """INSERT INTO feeds (id, name, url, etag, modified_at, fetched_at, created_at, weight, metadata, "group", refresh_interval)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    feed.id,
                    feed.name,
                    feed.url,
                    feed.etag,
                    feed.modified_at,
                    feed.fetched_at,
                    feed.created_at,
                    feed.weight,
                    feed.metadata,
                    feed.group,
                    feed.refresh_interval,
                ),
            )
            conn.commit()
            return (feed, True)  # is new


def update_feed(
    feed_id: str,
    fetched_at: str,
    etag: str | None = None,
    modified_at: str | None = None,
) -> bool:
    """Update feed metadata after a successful fetch.

    Args:
        feed_id: The ID of the feed to update.
        fetched_at: The new fetched_at timestamp.
        etag: Optional ETag header value.
        modified_at: Optional Last-Modified header value.

    Returns:
        True if the feed was updated, False if not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        if etag is not None or modified_at is not None:
            cursor.execute(
                """UPDATE feeds SET fetched_at = ?, etag = COALESCE(?, etag), modified_at = COALESCE(?, modified_at)
                   WHERE id = ?""",
                (fetched_at, etag, modified_at, feed_id),
            )
        else:
            cursor.execute(
                "UPDATE feeds SET fetched_at = ? WHERE id = ?",
                (fetched_at, feed_id),
            )
        updated = cursor.rowcount > 0
        conn.commit()
        return updated


def update_feed_metadata(
    feed_id: str,
    weight: float | None = None,
    group: str | None = None,
    metadata: str | None = None,
    refresh_interval: int | None = None,
) -> tuple[Feed | None, bool]:
    """Update feed metadata (weight, group, metadata JSON, refresh_interval).

    Args:
        feed_id: The ID of the feed to update.
        weight: Optional new weight (0.0-1.0). If None, not updated.
        group: Optional new group name. If None, not updated.
            Use empty string to clear.
        metadata: Optional JSON metadata string. If None, not updated.
        refresh_interval: Optional refresh interval in seconds. If None, not updated.
            Must be >= 60 seconds.

    Returns:
        Tuple of (updated Feed object or None if not found, success bool).
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Build dynamic UPDATE query based on provided fields
        set_clauses = []
        params = []
        if weight is not None:
            set_clauses.append("weight = ?")
            params.append(weight)
        if group is not None:
            set_clauses.append('"group" = ?')
            params.append(group)
        if metadata is not None:
            set_clauses.append("metadata = ?")
            params.append(metadata)
        if refresh_interval is not None:
            set_clauses.append("refresh_interval = ?")
            params.append(refresh_interval)

        if not set_clauses:
            # No fields to update, just return current feed
            return get_feed(feed_id), False

        params.append(feed_id)
        set_sql = ", ".join(set_clauses)

        cursor.execute(
            f"""UPDATE feeds SET {set_sql} WHERE id = ?""",
            tuple(params),
        )
        updated = cursor.rowcount > 0
        conn.commit()

        if not updated:
            return None, False

        # Return updated Feed object (fetch fresh from DB)
        return get_feed(feed_id), True
