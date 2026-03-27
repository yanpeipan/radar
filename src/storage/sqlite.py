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
    with get_db() as conn:
        cursor = conn.cursor()

        # Feeds table: stores RSS/Atom feed sources
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                etag TEXT,
                last_modified TEXT,
                last_fetched TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                weight REAL DEFAULT 0.3
            )
        """)

        # Articles table: stores individual feed items
        # Note: id is NOT PRIMARY KEY - same article can exist in multiple feeds
        # with UNIQUE(feed_id, id) constraint
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT NOT NULL,
                feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                title TEXT,
                link TEXT,
                guid TEXT NOT NULL,
                pub_date TEXT,
                description TEXT,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(feed_id, id)
            )
        """)

        # Indexes for common query patterns
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_pub_date ON articles(pub_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_link ON articles(link)")

        # FTS5 virtual table for full-text search
        # Uses porter tokenizer for English stemming
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title,
                description,
                content,
                tokenize='porter ascii'
            )
        """)

        conn.commit()


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


def _load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension."""
    conn.enable_load_extension(True)
    try:
        conn.load_extension("vec0")
    except sqlite3.OperationalError:
        pass  # vec0 may not be available


def _ensure_embeddings_table() -> None:
    """Create article_embeddings table if not exists."""
    with get_db() as conn:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_embeddings (
                article_id TEXT PRIMARY KEY,
                embedding BLOB
            )
        """)
        conn.commit()


def store_embedding(article_id: str, embedding) -> None:
    """Store article embedding in sqlite-vec."""
    import numpy as np
    _ensure_embeddings_table()
    with get_db() as conn:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        embedding_bytes = embedding.tobytes()
        cursor.execute("""
            INSERT OR REPLACE INTO article_embeddings (article_id, embedding)
            VALUES (?, ?)
        """, (article_id, embedding_bytes))
        conn.commit()


def get_article_embedding(article_id: str):
    """Retrieve stored embedding for an article."""
    import numpy as np
    with get_db() as conn:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT embedding FROM article_embeddings WHERE article_id = ?", (article_id,))
        row = cursor.fetchone()
        if row:
            return np.frombuffer(row["embedding"], dtype=np.float32)
        return None


def get_all_embeddings() -> tuple[list[str], list]:
    """Get all article embeddings for clustering.

    Returns:
        Tuple of (article_ids, embeddings_array).
    """
    import numpy as np
    with get_db() as conn:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT article_id, embedding FROM article_embeddings")
        rows = cursor.fetchall()
        article_ids = [row["article_id"] for row in rows]
        embeddings = np.array([np.frombuffer(row["embedding"], dtype=np.float32) for row in rows])
        return article_ids, embeddings


def get_articles_without_embeddings() -> list[str]:
    """Get IDs of articles that don't have embeddings yet."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id FROM articles a
            LEFT JOIN article_embeddings ae ON a.id = ae.article_id
            WHERE ae.article_id IS NULL
        """)
        return [row["id"] for row in cursor.fetchall()]


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


def list_articles(limit: int = 20, feed_id: Optional[str] = None) -> list:
    """List articles ordered by publication date."""
    from src.application.articles import ArticleListItem
    with get_db() as conn:
        cursor = conn.cursor()
        if feed_id:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.feed_id = ?
                ORDER BY a.pub_date DESC, a.created_at DESC
                LIMIT ?
                """,
                (feed_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                ORDER BY a.pub_date DESC, a.created_at DESC
                LIMIT ?
                """,
                (limit,),
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


def get_articles_by_urls(urls: list[str]) -> list:
    """Get articles by URLs (guids) in batch.

    Args:
        urls: List of article URLs (stored as guid in SQLite)

    Returns:
        List of article dicts with all fields. Missing entries are omitted.
    """
    if not urls:
        return []
    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(urls))
        cursor.execute(
            f"""SELECT a.id, a.feed_id, f.name AS feed_name, a.title, a.link, a.guid,
                       a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.guid IN ({placeholders})""",
            urls,
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


def search_articles(query: str, limit: int = 20, feed_id: Optional[str] = None) -> list:
    """Search articles using FTS5 full-text search."""
    from src.application.articles import ArticleListItem
    if not query or not query.strip():
        return []
    with get_db() as conn:
        cursor = conn.cursor()
        if feed_id:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE articles_fts MATCH ?
                  AND a.feed_id = ?
                ORDER BY bm25(articles_fts)
                LIMIT ?
                """,
                (query, feed_id, limit),
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
