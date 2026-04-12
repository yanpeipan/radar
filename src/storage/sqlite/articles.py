"""Article storage module for SQLite.

Provides CRUD operations for articles including upsert, list, get, update,
and FTS search capabilities.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from nanoid import generate

from src.storage.sqlite.conn import _get_db_write_lock
from src.storage.sqlite.utils import (
    _date_to_str,
    _date_to_str_end,
    _normalize_published_at,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_article_field(article, field: str, default=None):
    """Get article field, handling both dict and dataclass Article."""
    if hasattr(article, field):
        return getattr(article, field)
    return article.get(field, default) if isinstance(article, dict) else default


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


def store_article(
    guid: str,
    title: str,
    content: str,
    link: str,
    feed_id: str | None = None,
    published_at: str | None = None,
    description: str | None = None,
    author: str | None = None,
    tags: str | None = None,
    category: str | None = None,
) -> str:
    """Store an article (insert or update based on guid existence).

    Args:
        guid: Unique identifier for the article.
        title: Article title.
        content: Article content (markdown/html).
        link: URL to the article.
        feed_id: Feed ID if from RSS feed (optional).
        published_at: Publication date (optional).
        description: Article description/summary (optional).
        author: Author name(s), comma-separated if multiple (optional).
        tags: Comma-separated tags (optional).
        category: Comma-separated categories (optional).

    Returns:
        article_id: The ID of the stored article.
    """
    from src.application.config import get_timezone
    from src.storage.sqlite.conn import get_db

    tz = get_timezone()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    normalized_published_at = _normalize_published_at(published_at, tz)

    with get_db() as conn:
        cursor = conn.cursor()

        # Single UPSERT - insert or update on conflict
        article_id = generate()
        modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """INSERT INTO articles (id, feed_id, title, link, guid, published_at, content, description, created_at, modified_at, author, tags, category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(feed_id, guid) DO UPDATE SET
                   title = excluded.title,
                   content = excluded.content,
                   link = excluded.link,
                   published_at = excluded.published_at,
                   modified_at = excluded.modified_at,
                   description = excluded.description,
                   author = excluded.author,
                   tags = excluded.tags,
                   category = excluded.category
               RETURNING id""",
            (
                article_id,
                feed_id or "",
                title,
                link,
                guid,
                normalized_published_at,
                content,
                description,
                now,
                modified_at,
                author,
                tags,
                category,
            ),
        )
        result = cursor.fetchone()
        if result:
            article_id = result[0]

        # Sync to FTS5
        cursor.execute(
            """INSERT OR REPLACE INTO articles_fts(rowid, title, description, content, author, tags, category)
               SELECT rowid, title, description, content, author, tags, category FROM articles WHERE id = ?""",
            (article_id,),
        )

        conn.commit()
        return article_id


async def store_article_async(
    guid: str,
    title: str,
    content: str,
    link: str,
    feed_id: str | None = None,
    published_at: str | None = None,
    description: str | None = None,
    author: str | None = None,
    tags: str | None = None,
    category: str | None = None,
) -> str:
    """Async wrapper for store_article that serializes writes via asyncio.Lock + to_thread.

    This prevents 'database is locked' errors when multiple async tasks
    call store_article simultaneously.

    Args:
        Same as store_article()

    Returns:
        Same as store_article(): article_id
    """
    lock = _get_db_write_lock()
    async with lock:
        return await asyncio.to_thread(
            store_article,
            guid,
            title,
            content,
            link,
            feed_id,
            published_at,
            description,
            author,
            tags,
            category,
        )


def _batch_upsert_articles(articles: list) -> list[tuple[str, str]]:
    """Batch upsert articles using single transaction with UPSERT.

    Args:
        articles: List of Article dataclass or dict objects with fields:
            guid, title, content, link, feed_id, published_at, description,
            author, tags, category, meta

    Returns:
        List of (article_id, guid) tuples for each article.
    """
    from src.storage.sqlite.conn import get_db

    if not articles:
        return []

    from src.application.config import get_timezone

    tz = get_timezone()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    results = []

    with get_db() as conn:
        cursor = conn.cursor()

        # Generate article IDs upfront
        article_ids = [generate() for _ in articles]

        # Prepare batch data
        batch_values = []
        for i, article in enumerate(articles):
            article_id = article_ids[i]
            meta = _get_article_field(article, "meta", {})
            meta_json = json.dumps(meta) if meta else None
            normalized_published_at = _normalize_published_at(
                _get_article_field(article, "published_at"), tz
            )
            batch_values.append(
                (
                    article_id,
                    _get_article_field(article, "feed_id") or "",
                    _get_article_field(article, "title") or "",
                    _get_article_field(article, "link") or "",
                    _get_article_field(article, "guid"),
                    normalized_published_at,
                    _get_article_field(article, "content"),
                    _get_article_field(article, "description"),
                    now,  # created_at
                    now,  # modified_at
                    _get_article_field(article, "author"),
                    _get_article_field(article, "tags"),
                    _get_article_field(article, "category"),
                    meta_json,
                )
            )

        _logger = logging.getLogger(__name__)
        _logger.debug(f"Batch upsert: preparing {len(articles)} articles for DB insert")

        # Batch UPSERT with RETURNING clause - single transaction, no second round-trip
        # Collect results after each execute (fetchall() only returns last query results)
        actual_ids_map: dict[tuple[str, str], str] = {}
        for batch_row in batch_values:
            cursor.execute(
                """INSERT INTO articles (id, feed_id, title, link, guid, published_at, content, description, created_at, modified_at, author, tags, category, meta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(feed_id, guid) DO UPDATE SET
                       title = excluded.title,
                       link = excluded.link,
                       published_at = excluded.published_at,
                       content = excluded.content,
                       description = excluded.description,
                       modified_at = excluded.modified_at,
                       author = excluded.author,
                       tags = excluded.tags,
                       category = excluded.category,
                       meta = excluded.meta
                   RETURNING id, feed_id, guid""",
                batch_row,
            )
            for row in cursor.fetchall():
                actual_ids_map[(row[1], row[2])] = row[0]
        _logger.debug(f"Batch upsert: inserted/updated {len(actual_ids_map)} articles")

        # Batch FTS sync - single query for all articles
        if article_ids:
            placeholders = ",".join("?" * len(article_ids))
            cursor.execute(  # nosec B608
                f"""INSERT OR REPLACE INTO articles_fts(rowid, title, description, content, author, tags, category)
                   SELECT rowid, title, description, content, author, tags, category FROM articles WHERE id IN ({placeholders})""",
                tuple(article_ids),
            )
            _logger.debug(
                f"Batch upsert: FTS index updated for {len(article_ids)} articles"
            )

        conn.commit()
        _logger.debug(
            f"Batch upsert: transaction committed, {len(articles)} articles processed"
        )

        # Build results with ACTUAL IDs from RETURNING
        results.clear()
        for i, article in enumerate(articles):
            feed_id = _get_article_field(article, "feed_id") or ""
            guid = _get_article_field(article, "guid")
            actual_id = actual_ids_map.get((feed_id, guid), article_ids[i])
            results.append((actual_id, guid))

        return results


def upsert_articles(articles: list[dict]) -> list[tuple[str, str]]:
    """Batch upsert articles using single transaction with UPSERT.

    Args:
        articles: List of article dicts with keys: guid, title, content, link, feed_id, published_at, description, author, tags, category

    Returns:
        List of (article_id, guid) tuples for each article.
    """
    return _batch_upsert_articles(articles)


async def upsert_articles_async(articles: list[dict]) -> list[tuple[str, str]]:
    """Async batch upsert articles with single transaction.

    Args:
        articles: List of article dicts with keys: guid, title, content, link, feed_id, published_at, description, author, tags, category

    Returns:
        List of (article_id, guid) tuples for each article.
    """
    if not articles:
        return []

    lock = _get_db_write_lock()
    async with lock:
        return await asyncio.to_thread(_batch_upsert_articles, articles)


# ---------------------------------------------------------------------------
# Query / list
# ---------------------------------------------------------------------------


def list_articles(
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    sort_by: str | None = None,
    min_quality: float | None = None,
) -> list:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
        sort_by: "quality" to sort by quality_score DESC, NULLS LAST.
        min_quality: Minimum quality_score filter (0.0-1.0).
    """
    import math
    from datetime import datetime, timezone

    from src.application.articles import ArticleListItem
    from src.application.config import get_timezone
    from src.storage.sqlite.conn import get_db
    from src.storage.vector import _published_at_to_timestamp

    tz = get_timezone()

    # Build WHERE clause
    conditions = []
    params = []
    if feed_id:
        conditions.append("a.feed_id = ?")
        params.append(feed_id)
    if since:
        conditions.append("a.published_at >= ?")
        params.append(_date_to_str(since, tz))
    if until:
        conditions.append("a.published_at <= ?")
        params.append(_date_to_str_end(until, tz))
    if on:
        # Match articles within each specified date (start-of-day to end-of-day)
        for d in on:
            start = _date_to_str(d, tz)
            end = _date_to_str_end(d, tz)
            conditions.append("a.published_at BETWEEN ? AND ?")
            params.extend([start, end])
    if groups:
        placeholders = ",".join("?" * len(groups))
        conditions.append(f'f."group" IN ({placeholders})')
        params.extend(groups)
    if min_quality is not None:
        conditions.append("a.quality_score >= ?")
        params.append(min_quality)
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Build ORDER BY
    if sort_by == "quality":
        order_by = "a.quality_score DESC, a.published_at DESC"
    else:
        order_by = "a.published_at DESC, a.created_at DESC"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(  # nosec B608
            f"""
            SELECT a.id, a.feed_id, f.name as feed_name, f.weight as feed_weight,
                   a.title, a.link, a.guid, a.published_at, a.description, a.content,
                   a.summary, a.quality_score, f.url as feed_url,
                   a.content_hash, a.minhash_signature
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT ?
            """,
            [*params, limit],
        )
        rows = cursor.fetchall()

        compute_freshness = sort_by == "quality"

        def _compute_article_item(row):
            freshness = 0.0
            if compute_freshness:
                pub_ts = _published_at_to_timestamp(row["published_at"])
                if pub_ts:
                    pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                    days_ago = (datetime.now(timezone.utc) - pub_dt).days
                    freshness = math.exp(-days_ago / 7)  # half_life_days = 7
            return ArticleListItem(
                id=row["id"],
                feed_id=row["feed_id"],
                feed_name=row["feed_name"],
                title=row["title"],
                link=row["link"],
                guid=row["guid"],
                published_at=row["published_at"],
                description=row["description"],
                vec_sim=0.0,
                bm25_score=0.0,
                freshness=freshness,
                source_weight=0.3,
                ce_score=0.0,
                score=0.0,
                quality_score=row["quality_score"],
                content=row["content"],
                summary=row["summary"],
                feed_weight=row["feed_weight"],
                feed_url=row["feed_url"],
                content_hash=row["content_hash"],
                minhash_signature=row["minhash_signature"],
            )

        return [_compute_article_item(row) for row in rows]


def get_article(article_id: str) -> list | None:
    """Get a single article by ID."""
    from src.application.articles import ArticleListItem
    from src.storage.sqlite.conn import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                   a.guid, a.published_at, a.description
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.id = ?
            """,
            (article_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ArticleListItem(
            id=row["id"],
            feed_id=row["feed_id"],
            feed_name=row["feed_name"],
            title=row["title"],
            link=row["link"],
            guid=row["guid"],
            published_at=row["published_at"],
            description=row["description"],
        )


def get_article_id_by_url(url: str) -> str | None:
    """Get article nanoid by URL (guid).

    Args:
        url: The article URL (stored as guid in SQLite)

    Returns:
        The SQLite article nanoid (id), or None if not found.
    """
    from src.storage.sqlite.conn import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM articles WHERE guid = ?", (url,))
        row = cursor.fetchone()
        return row["id"] if row else None


def get_articles_by_ids(ids: list[str]) -> list:
    """Get articles by SQLite nanoid in batch.

    Args:
        ids: List of article SQLite nanoids (id)

    Returns:
        List of article dicts with all fields. Missing entries are omitted.
    """
    from src.storage.sqlite.conn import get_db

    if not ids:
        return []
    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(  # nosec B608
            f"""SELECT a.id, a.feed_id, f.name AS feed_name, f."group" AS feed_group,
                       a.title, a.link, a.guid, a.published_at, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.id IN ({placeholders})""",
            ids,
        )
        return [dict(row) for row in cursor.fetchall()]


def get_article_detail(article_id: str) -> dict | None:
    """Get full article details including content."""
    from src.storage.sqlite.conn import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        # First try exact match
        cursor.execute(
            """
            SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link, a.guid,
                   a.published_at, a.description, a.content, 'feed' as source_type
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.id = ?
            """,
            (article_id,),
        )
        row = cursor.fetchone()
        # If not found and length == 8, try truncated ID match
        if not row and len(article_id) == 8:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link, a.guid,
                       a.published_at, a.description, a.content, 'feed' as source_type
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.id LIKE ? || '%'
                LIMIT 1
                """,
                (article_id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "feed_id": row["feed_id"],
            "feed_name": row["feed_name"],
            "title": row["title"],
            "link": row["link"],
            "guid": row["guid"],
            "published_at": row["published_at"],
            "description": row["description"],
            "content": row["content"],
            "source_type": row["source_type"],
        }


def update_article_content(article_id: str, content: str) -> dict:
    """Update article content field and modified_at timestamp.

    Args:
        article_id: The article ID (supports 8-char truncated or full 32-char).
        content: The new content (Markdown from Trafilatura).

    Returns:
        Dict with 'success' (bool) and optional 'error' (str).
    """
    from src.storage.sqlite.conn import get_db

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        cursor = conn.cursor()
        # Build target ID: exact match or truncated 8-char prefix
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
        cursor.execute(
            "UPDATE articles SET content = ?, modified_at = ? WHERE id = ?",
            (content, now, actual_id),
        )
        conn.commit()
        return {"success": True, "error": None}
