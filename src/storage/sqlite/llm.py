"""LLM-related article functions: summarization, quality scoring, and keyword extraction.

Extracts LLM processing logic from the main SQLite storage module for independent
use in summarization and batch-processing workflows.
"""

from __future__ import annotations

import json
import time

from src.storage.sqlite.conn import get_db


def update_article_llm(
    article_id: str,
    *,
    summary: str | None = None,
    quality_score: float | None = None,
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update article LLM fields: summary, quality_score, keywords, tags.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).
        summary: AI-generated summary text.
        quality_score: Quality score 0.0-1.0.
        keywords: List of extracted keywords.
        tags: List of auto-generated tags.

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        if len(article_id) == 8:
            cursor.execute(
                "SELECT id FROM articles WHERE id LIKE ? || '%' LIMIT 1", (article_id,)
            )
        else:
            cursor.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": f"Article not found: {article_id}"}
        actual_id = row["id"]

        keywords_json = json.dumps(keywords) if keywords is not None else None
        tags_json = json.dumps(tags) if tags is not None else None

        cursor.execute(
            """
            UPDATE articles
            SET summary = ?, quality_score = ?, keywords = ?, tags = ?, summarized_at = ?
            WHERE id = ?
            """,
            (summary, quality_score, keywords_json, tags_json, now, actual_id),
        )
        conn.commit()
        return {"success": True, "error": None}


def get_article_with_llm(article_id: str) -> dict | None:
    """Get article with all LLM fields populated.

    Args:
        article_id: The article ID.

    Returns:
        Dict with article fields + LLM fields (summary, quality_score, keywords, tags, summarized_at),
        or None if not found.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.*, f.name as feed_name, f.weight as feed_weight, f.url as feed_url
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.id = ?
            """,
            (article_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        result = dict(row)
        # Parse JSON fields
        if result.get("keywords"):
            try:
                result["keywords"] = json.loads(result["keywords"])
            except Exception:
                result["keywords"] = []
        else:
            result["keywords"] = []

        if result.get("tags"):
            try:
                result["tags"] = json.loads(result["tags"])
            except Exception:
                result["tags"] = []
        else:
            result["tags"] = []
        return result
