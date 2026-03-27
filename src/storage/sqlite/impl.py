"""Database module for RSS reader.

Provides SQLite database connection with WAL mode and schema initialization.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from nanoid import generate

# Asyncio lock for serializing database writes from async context
_db_write_lock: asyncio.Lock | None = None


def _get_db_write_lock() -> asyncio.Lock:
    """Get or create the singleton asyncio.Lock for serializing DB writes."""
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock


logger = logging.getLogger(__name__)

import platformdirs


# Cross-platform database path using platformdirs
_DB_DIR = platformdirs.user_data_dir(appname="rss-reader", appauthor=False)
_DB_PATH = Path(_DB_DIR) / "rss-reader.db"


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


def store_article(
    guid: str,
    title: str,
    content: str,
    link: str,
    feed_id: Optional[str] = None,
    pub_date: Optional[str] = None,
) -> str:
    """Store an article (insert or update based on guid existence).

    Args:
        guid: Unique identifier for the article.
        title: Article title.
        content: Article content (markdown/html).
        link: URL to the article.
        feed_id: Feed ID if from RSS feed (optional).
        pub_date: Publication date (optional).

    Returns:
        Article ID (existing if updated, new if inserted).
    """
    from datetime import datetime
    from src.application.config import get_timezone

    now = datetime.now(get_timezone()).isoformat()

    with get_db() as conn:
        cursor = conn.cursor()

        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE guid = ?", (guid,))
        existing = cursor.fetchone()

        if existing:
            # UPDATE existing article
            article_id = existing["id"]
            cursor.execute(
                """UPDATE articles SET title = ?, content = ?, link = ?, pub_date = ?
                   WHERE guid = ?""",
                (title, content, link, pub_date or now, guid),
            )
        else:
            # INSERT new article
            article_id = generate()
            cursor.execute(
                """INSERT INTO articles (id, feed_id, title, link, guid, pub_date, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article_id,
                    feed_id or "",
                    title,
                    link,
                    guid,
                    pub_date or now,
                    content,
                    now,
                ),
            )

        # Sync to FTS5
        cursor.execute(
            """INSERT OR REPLACE INTO articles_fts(rowid, title, description, content)
               SELECT rowid, title, description, content FROM articles WHERE id = ?""",
            (article_id,),
        )

        conn.commit()
        return article_id


async def store_article_async(
    guid: str,
    title: str,
    content: str,
    link: str,
    feed_id: Optional[str] = None,
    pub_date: Optional[str] = None,
) -> str:
    """Async wrapper for store_article that serializes writes via asyncio.Lock + to_thread.

    This prevents 'database is locked' errors when multiple async tasks
    call store_article simultaneously.

    Args:
        Same as store_article()

    Returns:
        Same as store_article()
    """
    lock = _get_db_write_lock()
    async with lock:
        return await asyncio.to_thread(
            store_article, guid, title, content, link, feed_id, pub_date
        )


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
            """INSERT INTO feeds (id, name, url, etag, last_modified, last_fetched, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (feed.id, feed.name, feed.url, feed.etag, feed.last_modified, feed.last_fetched, feed.created_at)
        )
        conn.commit()
        return feed


def list_feeds() -> list:
    """List all feeds with article counts."""
    from src.models import Feed
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.name, f.url, f.etag, f.last_modified, f.last_fetched, f.created_at,
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
                last_modified=row["last_modified"],
                last_fetched=row["last_fetched"],
                created_at=row["created_at"],
            )
            feed.articles_count = row["articles_count"]
            feeds.append(feed)
        return feeds


def get_feed(feed_id: str) -> Optional[Feed]:
    """Get single feed by ID."""
    from src.models import Feed
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, url, etag, last_modified, last_fetched, created_at, weight FROM feeds WHERE id = ?",
            (feed_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Feed(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            etag=row["etag"],
            last_modified=row["last_modified"],
            last_fetched=row["last_fetched"],
            created_at=row["created_at"],
            weight=row["weight"],
        )


def remove_feed(feed_id: str) -> bool:
    """Delete feed by ID. Returns True if deleted."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def list_articles(limit: int = 20, feed_id: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None, on: Optional[list[str]] = None) -> list:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
    """
    from src.application.articles import ArticleListItem

    # Build WHERE clause
    conditions = []
    params = []
    if feed_id:
        conditions.append("a.feed_id = ?")
        params.append(feed_id)
    if since:
        conditions.append("DATE(a.pub_date) >= DATE(?)")
        params.append(since)
    if until:
        conditions.append("DATE(a.pub_date) <= DATE(?)")
        params.append(until)
    if on:
        placeholders = ",".join("?" * len(on))
        conditions.append(f"DATE(a.pub_date) IN ({placeholders})")
        params.extend(on)
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT a.id, a.feed_id, f.name as feed_name,
                   a.title, a.link, a.guid, a.pub_date, a.description
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE {where_clause}
            ORDER BY a.pub_date DESC, a.created_at DESC
            LIMIT ?
            """,
            [*params, limit],
        )
        rows = cursor.fetchall()
        return [
            ArticleListItem(
                id=row["id"],
                feed_id=row["feed_id"],
                feed_name=row["feed_name"],
                title=row["title"],
                link=row["link"],
                guid=row["guid"],
                pub_date=row["pub_date"],
                description=row["description"],
            )
            for row in rows
        ]


def get_article(article_id: str) -> Optional[list]:
    """Get a single article by ID."""
    from src.application.articles import ArticleListItem
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                   a.guid, a.pub_date, a.description
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
            pub_date=row["pub_date"],
            description=row["description"],
        )


def get_article_id_by_url(url: str) -> Optional[str]:
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
        cursor.execute(
            f"""SELECT a.id, a.feed_id, f.name AS feed_name, a.title, a.link, a.guid,
                       a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.id IN ({placeholders})""",
            ids,
        )
        return [dict(row) for row in cursor.fetchall()]


def get_article_detail(article_id: str) -> Optional[dict]:
    """Get full article details including content."""
    with get_db() as conn:
        cursor = conn.cursor()
        # First try exact match
        cursor.execute(
            """
            SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link, a.guid,
                   a.pub_date, a.description, a.content, 'feed' as source_type
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
                       a.pub_date, a.description, a.content, 'feed' as source_type
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
            "pub_date": row["pub_date"],
            "description": row["description"],
            "content": row["content"],
            "source_type": row["source_type"],
        }


def search_articles(query: str, limit: int = 20, feed_id: Optional[str] = None, since: Optional[str] = None, until: Optional[str] = None, on: Optional[list[str]] = None) -> list:
    """Search articles using FTS5 full-text search.

    Args:
        query: Search query string.
        limit: Maximum number of results.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
    """
    from src.application.articles import ArticleListItem
    if not query or not query.strip():
        return []

    # Build WHERE clause for date filtering
    date_conditions = []
    date_params = []
    if since:
        date_conditions.append("DATE(a.pub_date) >= DATE(?)")
        date_params.append(since)
    if until:
        date_conditions.append("DATE(a.pub_date) <= DATE(?)")
        date_params.append(until)
    if on:
        placeholders = ",".join("?" * len(on))
        date_conditions.append(f"DATE(a.pub_date) IN ({placeholders})")
        date_params.extend(on)
    date_clause = " AND ".join(date_conditions) if date_conditions else None

    with get_db() as conn:
        cursor = conn.cursor()
        if feed_id:
            where_parts = ["articles_fts MATCH ?", "a.feed_id = ?"]
            params = [query, feed_id]
            if date_clause:
                where_parts.append(date_clause)
                params.extend(date_params)
            where_sql = " AND ".join(where_parts)
            cursor.execute(
                f"""
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE {where_sql}
                ORDER BY bm25(articles_fts)
                LIMIT ?
                """,
                [*params, limit],
            )
        else:
            if date_clause:
                cursor.execute(
                    f"""
                    SELECT a.id, a.feed_id, f.name as feed_name,
                           a.title, a.link, a.guid, a.pub_date, a.description
                    FROM articles_fts
                    JOIN articles a ON articles_fts.rowid = a.rowid
                    JOIN feeds f ON a.feed_id = f.id
                    WHERE articles_fts MATCH ? AND {date_clause}
                    ORDER BY bm25(articles_fts)
                    LIMIT ?
                    """,
                    [query, *date_params, limit],
                )
            else:
                cursor.execute(
                    """
                    SELECT a.id, a.feed_id, f.name as feed_name,
                           a.title, a.link, a.guid, a.pub_date, a.description
                    FROM articles_fts
                    JOIN articles a ON articles_fts.rowid = a.rowid
                    JOIN feeds f ON a.feed_id = f.id
                    WHERE articles_fts MATCH ?
                    ORDER BY bm25(articles_fts)
                    LIMIT ?
                    """,
                    (query, limit),
                )
        return [
            ArticleListItem(
                id=row["id"],
                feed_id=row["feed_id"],
                feed_name=row["feed_name"],
                title=row["title"],
                link=row["link"],
                guid=row["guid"],
                pub_date=row["pub_date"],
                description=row["description"],
            )
            for row in cursor.fetchall()
        ]


def ensure_crawled_feed() -> None:
    """Create 'crawled' system feed if it doesn't exist."""
    from src.application.config import get_timezone
    from datetime import datetime
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM feeds WHERE id = 'crawled'")
        if cursor.fetchone() is None:
            now = datetime.now(get_timezone()).isoformat()
            cursor.execute(
                """INSERT INTO feeds (id, name, url, created_at)
                   VALUES ('crawled', 'Crawled Pages', '', ?)""",
                (now,)
            )
            conn.commit()
