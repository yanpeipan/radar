"""Article status functions: mark read/unread and toggle star/bookmark.

Provides storage-level operations for read/unread tracking and article
bookmarking (starring). All functions support both 8-char truncated and
full 32-char article IDs for ergonomic CLI usage.
"""

from __future__ import annotations

import time

from src.storage.sqlite.conn import get_db


def _resolve_article_id(cursor, article_id: str) -> str | None:
    """Resolve article ID, supporting 8-char truncated or full 32-char.

    Args:
        cursor: Database cursor.
        article_id: The article ID to resolve.

    Returns:
        The resolved full article ID, or None if not found.
    """
    if len(article_id) == 8:
        cursor.execute(
            "SELECT id FROM articles WHERE id LIKE ? || '%' LIMIT 1", (article_id,)
        )
    else:
        cursor.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
    row = cursor.fetchone()
    return row["id"] if row else None


def mark_article_read(article_id: str) -> dict:
    """Mark an article as read by setting the read_at timestamp.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        actual_id = _resolve_article_id(cursor, article_id)
        if actual_id is None:
            return {"success": False, "error": f"Article not found: {article_id}"}

        cursor.execute(
            "UPDATE articles SET read_at = ? WHERE id = ?",
            (now, actual_id),
        )
        conn.commit()
        return {"success": True, "error": None}


def mark_article_unread(article_id: str) -> dict:
    """Mark an article as unread by clearing the read_at timestamp.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        actual_id = _resolve_article_id(cursor, article_id)
        if actual_id is None:
            return {"success": False, "error": f"Article not found: {article_id}"}

        cursor.execute(
            "UPDATE articles SET read_at = NULL WHERE id = ?",
            (actual_id,),
        )
        conn.commit()
        return {"success": True, "error": None}


def _set_article_star(article_id: str, starred: bool) -> dict:
    """Set the star/bookmark state of an article.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).
        starred: True to star the article, False to unstar.

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        actual_id = _resolve_article_id(cursor, article_id)
        if actual_id is None:
            return {"success": False, "error": f"Article not found: {article_id}"}

        cursor.execute(
            "UPDATE articles SET is_starred = ? WHERE id = ?",
            (1 if starred else 0, actual_id),
        )
        conn.commit()
        return {"success": True, "error": None}


def star_article(article_id: str) -> dict:
    """Star/bookmark an article.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    return _set_article_star(article_id, starred=True)


def unstar_article(article_id: str) -> dict:
    """Remove star/bookmark from an article.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    return _set_article_star(article_id, starred=False)


def toggle_article_star(article_id: str) -> dict:
    """Toggle the star/bookmark state of an article.

    If the article is not starred, it becomes starred (is_starred = 1).
    If it is already starred, it becomes unstarred (is_starred = 0).

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).

    Returns:
        Dict with 'success' (bool), optional 'error' (str),
        and 'is_starred' (bool) indicating the new state.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        actual_id = _resolve_article_id(cursor, article_id)
        if actual_id is None:
            return {
                "success": False,
                "error": f"Article not found: {article_id}",
                "is_starred": None,
            }

        # Read current state
        cursor.execute(
            "SELECT is_starred FROM articles WHERE id = ?",
            (actual_id,),
        )
        row = cursor.fetchone()
        current = row["is_starred"] if row else None

        # Toggle: NULL/0 -> 1, 1 -> 0
        new_state = 0 if (current == 1) else 1

        cursor.execute(
            "UPDATE articles SET is_starred = ? WHERE id = ?",
            (new_state, actual_id),
        )
        conn.commit()
        return {"success": True, "error": None, "is_starred": bool(new_state)}
