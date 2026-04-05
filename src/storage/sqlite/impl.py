"""Database module for RSS reader.

Provides SQLite database connection with WAL mode and schema initialization.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from nanoid import generate

from src.models import Feed

# Asyncio lock for serializing database writes from async context
_db_write_lock: asyncio.Lock | None = None


def _get_db_write_lock() -> asyncio.Lock:
    """Get or create the singleton asyncio.Lock for serializing DB writes."""
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock


logger = logging.getLogger(__name__)

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

    tz = get_timezone()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    normalized_published_at = _normalize_published_at(published_at, tz)

    with get_db() as conn:
        cursor = conn.cursor()

        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE guid = ?", (guid,))
        existing = cursor.fetchone()

        if existing:
            # UPDATE existing article
            article_id = existing["id"]
            modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """UPDATE articles SET title = ?, content = ?, link = ?, published_at = ?, modified_at = ?, description = ?, author = ?, tags = ?, category = ?
                   WHERE guid = ?""",
                (
                    title,
                    content,
                    link,
                    normalized_published_at,
                    modified_at,
                    description,
                    author,
                    tags,
                    category,
                    guid,
                ),
            )
        else:
            # INSERT new article
            article_id = generate()
            modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """INSERT INTO articles (id, feed_id, title, link, guid, published_at, content, description, created_at, modified_at, author, tags, category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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


def _get_article_field(article, field: str, default=None):
    """Get article field, handling both dict and dataclass Article."""
    if hasattr(article, field):
        return getattr(article, field)
    return article.get(field, default) if isinstance(article, dict) else default


def _batch_upsert_articles(articles: list) -> list[tuple[str, str]]:
    """Batch upsert articles using single transaction with UPSERT.

    Args:
        articles: List of Article dataclass or dict objects with fields:
            guid, title, content, link, feed_id, published_at, description,
            author, tags, category, meta

    Returns:
        List of (article_id, guid) tuples for each article.
    """
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

        # Batch UPSERT with executemany - single transaction
        cursor.executemany(
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
                   meta = excluded.meta""",
            batch_values,
        )
        _logger.debug(f"Batch upsert: inserted/updated {len(batch_values)} articles")

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
            f"Batch upsert: transaction committed, {len(results)} articles processed"
        )

        # Build results
        for i, article in enumerate(articles):
            results.append((article_ids[i], _get_article_field(article, "guid")))

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


def feed_exists(url: str) -> bool:
    """Check if feed with given URL exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM feeds WHERE url = ?", (url,))
        return cursor.fetchone() is not None


def add_feed(feed) -> Feed:
    """Insert new feed, return Feed object."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO feeds (id, name, url, etag, modified_at, fetched_at, created_at, weight)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                feed.id,
                feed.name,
                feed.url,
                feed.etag,
                feed.modified_at,
                feed.fetched_at,
                feed.created_at,
                feed.weight,
            ),
        )
        conn.commit()
        return feed


def list_feeds() -> list:
    """List all feeds with article counts."""
    from src.models import Feed

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.name, f.url, f.etag, f.modified_at, f.fetched_at, f.created_at, f.weight, f."group",
                   COUNT(a.id) as articles_count
            FROM feeds f
            LEFT JOIN articles a ON f.id = a.feed_id
            GROUP BY f.id
            ORDER BY f.created_at DESC
        """)
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
            )
            feed.articles_count = row["articles_count"]
            feeds.append(feed)
        return feeds


def get_feed(feed_id: str) -> Feed | None:
    """Get single feed by ID."""
    from src.models import Feed

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, url, etag, modified_at, fetched_at, created_at, weight, "group" FROM feeds WHERE id = ?',
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
        )


def get_feeds_by_ids(ids: list[str]) -> dict[str, Feed]:
    """Get feeds by IDs in batch, returning a dict mapping id -> Feed.

    Args:
        ids: List of feed IDs

    Returns:
        Dict mapping feed ID to Feed object. Missing entries are omitted.
    """
    from src.models import Feed

    if not ids:
        return {}
    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(  # nosec B608
            f'SELECT id, name, url, etag, modified_at, fetched_at, created_at, weight, "group" FROM feeds WHERE id IN ({placeholders})',
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
            )
            for row in cursor.fetchall()
        }


def remove_feed(feed_id: str) -> bool:
    """Delete feed by ID. Returns True if deleted."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def upsert_feed(feed) -> tuple[Feed, bool]:
    """Insert or update a feed by URL, returning the Feed object and whether it was new.

    If feed with same URL exists, preserves existing id and updates other fields.
    If not exists, inserts new feed.

    Args:
        feed: Feed object with all fields to save.

    Returns:
        Tuple of (saved Feed object, is_new) where is_new is True for insert, False for update.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, created_at FROM feeds WHERE url = ?", (feed.url,))
        existing = cursor.fetchone()

        if existing:
            # UPDATE existing feed, preserving original id
            cursor.execute(
                """UPDATE feeds SET name = ?, etag = ?, modified_at = ?, fetched_at = ?, weight = ?, metadata = ?, "group" = ?
                   WHERE url = ?""",
                (
                    feed.name,
                    feed.etag,
                    feed.modified_at,
                    feed.fetched_at,
                    feed.weight,
                    feed.metadata,
                    feed.group,
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
                ),
                False,  # not new
            )
        else:
            # INSERT new feed
            cursor.execute(
                """INSERT INTO feeds (id, name, url, etag, modified_at, fetched_at, created_at, weight, metadata, "group")
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                ),
            )
            conn.commit()
            return (feed, True)  # is new


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


def list_articles(
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
) -> list:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
    """
    import math
    from datetime import datetime, timezone

    from src.application.articles import ArticleListItem
    from src.application.config import get_timezone
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
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(  # nosec B608
            f"""
            SELECT a.id, a.feed_id, f.name as feed_name,
                   a.title, a.link, a.guid, a.published_at, a.description
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE {where_clause}
            ORDER BY a.published_at DESC, a.created_at DESC
            LIMIT ?
            """,
            [*params, limit],
        )
        rows = cursor.fetchall()

        def _compute_article_item(row):
            pub_ts = _published_at_to_timestamp(row["published_at"])
            freshness = 0.0
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
                final_score=0.0,
            )

        return [_compute_article_item(row) for row in rows]


def get_article(article_id: str) -> list | None:
    """Get a single article by ID."""
    from src.application.articles import ArticleListItem

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


def search_articles_fts(
    query: str,
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
) -> list:
    """Search articles using FTS5 full-text search.

    Args:
        query: Search query string.
        limit: Maximum number of results.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
    """
    import math

    from src.application.articles import ArticleListItem
    from src.application.config import get_bm25_factor, get_timezone

    if not query or not query.strip():
        return []

    tz = get_timezone()

    # Build WHERE clause for date filtering (using timestamp comparison)
    date_conditions = []
    date_params = []
    if since:
        date_conditions.append("a.published_at >= ?")
        date_params.append(_date_to_timestamp(since, tz))
    if until:
        date_conditions.append("a.published_at <= ?")
        date_params.append(_date_to_timestamp_end(until, tz))
    if on:
        on_timestamps = [_date_to_timestamp(d, tz) for d in on]
        placeholders = ",".join("?" * len(on_timestamps))
        date_conditions.append(f"a.published_at IN ({placeholders})")
        date_params.extend(on_timestamps)
    date_clause = " AND ".join(date_conditions) if date_conditions else None

    with get_db() as conn:
        cursor = conn.cursor()
        if feed_id:
            where_parts = ["articles_fts MATCH ?", "a.feed_id = ?"]
            params = [query, feed_id]
            if date_clause:
                where_parts.append(date_clause)
                params.extend(date_params)
            if groups:
                placeholders = ",".join("?" * len(groups))
                where_parts.append(f'f."group" IN ({placeholders})')
                params.extend(groups)
            where_sql = " AND ".join(where_parts)
            cursor.execute(  # nosec B608
                f"""
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.published_at, a.description,
                       bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE {where_sql}
                ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                LIMIT ?
                """,
                [*params, limit],
            )
        else:
            if groups:
                placeholders = ",".join("?" * len(groups))
                groups_clause = f'f."group" IN ({placeholders})'
                if date_clause:
                    cursor.execute(  # nosec B608
                        f"""
                        SELECT a.id, a.feed_id, f.name as feed_name,
                               a.title, a.link, a.guid, a.published_at, a.description,
                               bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                        FROM articles_fts
                        JOIN articles a ON articles_fts.rowid = a.rowid
                        JOIN feeds f ON a.feed_id = f.id
                        WHERE articles_fts MATCH ? AND {date_clause} AND {groups_clause}
                        ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                        LIMIT ?
                        """,
                        [query, *date_params, *groups, limit],
                    )
                else:
                    cursor.execute(  # nosec B608
                        f"""
                        SELECT a.id, a.feed_id, f.name as feed_name,
                               a.title, a.link, a.guid, a.published_at, a.description,
                               bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                        FROM articles_fts
                        JOIN articles a ON articles_fts.rowid = a.rowid
                        JOIN feeds f ON a.feed_id = f.id
                        WHERE articles_fts MATCH ? AND {groups_clause}
                        ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                        LIMIT ?
                        """,
                        [query, *groups, limit],
                    )
            elif date_clause:
                cursor.execute(  # nosec B608
                    f"""
                    SELECT a.id, a.feed_id, f.name as feed_name,
                           a.title, a.link, a.guid, a.published_at, a.description,
                           bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                    FROM articles_fts
                    JOIN articles a ON articles_fts.rowid = a.rowid
                    JOIN feeds f ON a.feed_id = f.id
                    WHERE articles_fts MATCH ? AND {date_clause}
                    ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                    LIMIT ?
                    """,
                    [query, *date_params, limit],
                )
            else:
                cursor.execute(
                    """
                    SELECT a.id, a.feed_id, f.name as feed_name,
                           a.title, a.link, a.guid, a.published_at, a.description,
                           bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                    FROM articles_fts
                    JOIN articles a ON articles_fts.rowid = a.rowid
                    JOIN feeds f ON a.feed_id = f.id
                    WHERE articles_fts MATCH ?
                    ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                    LIMIT ?
                    """,
                    (query, limit),
                )
        factor = get_bm25_factor()
        return [
            ArticleListItem(
                id=row["id"],
                feed_id=row["feed_id"],
                feed_name=row["feed_name"],
                title=row["title"],
                link=row["link"],
                guid=row["guid"],
                published_at=row["published_at"],
                description=row["description"],
                bm25_score=1 / (1 + math.exp(row["bm25_score"] * factor)),
            )
            for row in cursor.fetchall()
        ]


def update_feed(
    feed_id: str,
    fetched_at: str,
    etag: str | None = None,
    modified_at: str | None = None,
) -> bool:
    """Update feed metadata after a successful fetch.

    Returns True if feed was updated, False if not found.
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
