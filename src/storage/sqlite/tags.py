"""Tag CRUD operations for SQLite storage.

Provides functions for creating, reading, updating, and deleting tags
in the SQLite database.
"""

from __future__ import annotations

from src.models import Feed, Tag
from src.storage.sqlite.conn import get_db


def tag_exists(name: str) -> bool:
    """Check if a tag with the given name exists.

    Args:
        name: The tag name to check.

    Returns:
        True if a tag with the given name exists, False otherwise.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
        return cursor.fetchone() is not None


def add_tag(name: str, description: str | None = None) -> Tag:
    """Create a new tag and return the Tag object.

    The tag ID is generated as a UUID and created_at is set to the current time.

    Args:
        name: Display name of the tag (unique, max 100 chars).
        description: Optional description of the tag.

    Returns:
        The newly created Tag object.
    """
    import time
    import uuid

    tag_id = str(uuid.uuid4())
    created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    tag = Tag(id=tag_id, name=name, created_at=created_at, description=description)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tags (id, name, created_at, description) VALUES (?, ?, ?, ?)",
            (tag.id, tag.name, tag.created_at, tag.description),
        )
        conn.commit()
        return tag


def list_tags() -> list[Tag]:
    """List all tags ordered by name.

    Returns:
        List of Tag objects ordered by name ascending.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at, description FROM tags ORDER BY name ASC"
        )
        rows = cursor.fetchall()
        return [
            Tag(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
                description=row["description"],
            )
            for row in rows
        ]


def get_tag(tag_id: str) -> Tag | None:
    """Get a single tag by ID.

    Args:
        tag_id: The tag ID to look up.

    Returns:
        Tag object if found, None otherwise.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at, description FROM tags WHERE id = ?",
            (tag_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Tag(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            description=row["description"],
        )


def delete_tag(tag_id: str) -> bool:
    """Delete a tag by ID.

    Also removes all feed_tag associations for this tag.

    Args:
        tag_id: The ID of the tag to delete.

    Returns:
        True if the tag was deleted, False if it was not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feed_tags WHERE tag_id = ?", (tag_id,))
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def assign_tag_to_feed(feed_id: str, tag_name: str) -> Tag:
    """Assign a tag to a feed by name, creating the tag if it does not exist.

    Args:
        feed_id: The ID of the feed to tag.
        tag_name: The name of the tag to assign.

    Returns:
        The Tag object that was assigned.
    """
    tag = _get_tag_by_name(tag_name)
    if tag is None:
        tag = add_tag(tag_name)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO feed_tags (feed_id, tag_id) VALUES (?, ?)",
            (feed_id, tag.id),
        )
        conn.commit()
        return tag


def remove_tag_from_feed(feed_id: str, tag_name: str) -> bool:
    """Remove a tag assignment from a feed by name.

    Args:
        feed_id: The ID of the feed to untag.
        tag_name: The name of the tag to remove.

    Returns:
        True if the assignment was removed, False if it was not found.
    """
    tag = _get_tag_by_name(tag_name)
    if tag is None:
        return False

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM feed_tags WHERE feed_id = ? AND tag_id = ?",
            (feed_id, tag.id),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def get_tags_for_feed(feed_id: str) -> list[Tag]:
    """Get all tags assigned to a feed.

    Args:
        feed_id: The ID of the feed.

    Returns:
        List of Tag objects assigned to the feed, ordered by name.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.id, t.name, t.created_at, t.description
            FROM tags t
            INNER JOIN feed_tags ft ON t.id = ft.tag_id
            WHERE ft.feed_id = ?
            ORDER BY t.name ASC
            """,
            (feed_id,),
        )
        rows = cursor.fetchall()
        return [
            Tag(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
                description=row["description"],
            )
            for row in rows
        ]


def _get_tag_by_name(name: str) -> Tag | None:
    """Get a tag by name.

    Args:
        name: The tag name to look up.

    Returns:
        Tag object if found, None otherwise.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at, description FROM tags WHERE name = ?",
            (name,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Tag(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            description=row["description"],
        )


def get_feeds_by_tag(tag_name: str) -> list[Feed]:
    """Get all feeds assigned to a tag by name.

    Args:
        tag_name: The name of the tag.

    Returns:
        List of Feed objects assigned to the tag, ordered by creation date descending.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.name, f.url, f.etag, f.modified_at, f.fetched_at,
                   f.created_at, f.weight, f."group"
            FROM feeds f
            INNER JOIN feed_tags ft ON f.id = ft.feed_id
            INNER JOIN tags t ON ft.tag_id = t.id
            WHERE t.name = ?
            ORDER BY f.created_at DESC
            """,
            (tag_name,),
        )
        rows = cursor.fetchall()
        return [
            Feed(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                etag=row["etag"],
                modified_at=row["modified_at"],
                fetched_at=row["fetched_at"],
                created_at=row["created_at"],
                weight=row["weight"],
                group=row["group"],
            )
            for row in rows
        ]
