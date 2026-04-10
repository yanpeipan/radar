"""LLM-related article functions: summarization, quality scoring, and keyword extraction.

Extracts LLM processing logic from the main SQLite storage module for independent
use in summarization and batch-processing workflows.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone

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


def list_articles_for_llm(
    limit: int = 100,
    feed_id: str | None = None,
    groups: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    min_quality: float | None = None,
    unsummarized_only: bool = True,
) -> list[dict]:
    """List articles for LLM processing.

    Args:
        limit: Maximum number of articles to return.
        feed_id: Optional feed ID to filter by.
        groups: Optional list of feed groups to filter by.
        since: Optional start date (YYYY-MM-DD).
        until: Optional end date (YYYY-MM-DD).
        min_quality: Minimum quality score threshold.
        unsummarized_only: If True, only return articles without summaries.

    Returns:
        List of article dicts (without LLM fields filled).
    """
    from src.application.config import get_timezone
    from src.storage.sqlite.articles import _date_to_str, _date_to_str_end
    from src.storage.vector import _published_at_to_timestamp

    tz = get_timezone()

    conditions = []
    if unsummarized_only:
        conditions.append("(a.summary IS NULL OR a.summary = '')")
    params = []

    if feed_id:
        conditions.append("a.feed_id = ?")
        params.append(feed_id)
    if groups:
        placeholders = ",".join("?" * len(groups))
        conditions.append(f'f."group" IN ({placeholders})')
        params.extend(groups)
    if since:
        conditions.append("a.published_at >= ?")
        params.append(_date_to_str(since, tz))
    if until:
        conditions.append("a.published_at <= ?")
        params.append(_date_to_str_end(until, tz))

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT a.id, a.feed_id, f.name as feed_name, f.weight as feed_weight,
                   a.title, a.link, a.published_at, a.description, a.content,
                   a.summary, a.quality_score, a.keywords, a.tags, a.summarized_at,
                   f.url as feed_url
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE {where_clause}
            ORDER BY f.weight DESC, a.published_at DESC
            LIMIT ?
            """,
            [*params, limit],
        )
        rows = cursor.fetchall()

        def _compute_item(row):
            pub_ts = _published_at_to_timestamp(row["published_at"])
            freshness = 0.0
            if pub_ts:
                pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - pub_dt).days
                freshness = math.exp(-days_ago / 7)
            return {
                "id": row["id"],
                "feed_id": row["feed_id"],
                "feed_name": row["feed_name"],
                "feed_weight": row["feed_weight"],
                "title": row["title"],
                "link": row["link"],
                "published_at": row["published_at"],
                "description": row["description"],
                "content": row["content"],
                "summary": row["summary"],
                "quality_score": row["quality_score"],
                "keywords": row["keywords"],
                "tags": row["tags"],
                "summarized_at": row["summarized_at"],
                "feed_url": row["feed_url"],
                "freshness": freshness,
            }

        return [_compute_item(row) for row in rows]
