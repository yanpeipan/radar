"""Database module for RSS reader.

Provides SQLite database connection with WAL mode and schema initialization.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

import platformdirs

from src.models import Tag


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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

        # Tags table for article categorization
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Article tags table (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_tags (
                article_id TEXT NOT NULL,
                tag_id TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (article_id, tag_id),
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        """)

        # Index for tag lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_article_tags_tag_id ON article_tags(tag_id)")

        conn.commit()


def add_tag(name: str) -> Tag:
    """Create a new tag. Returns Tag object."""
    import uuid
    with get_db() as conn:
        cursor = conn.cursor()
        tag_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO tags (id, name) VALUES (?, ?)",
            (tag_id, name)
        )
        conn.commit()
        cursor.execute("SELECT created_at FROM tags WHERE id = ?", (tag_id,))
        created_at = cursor.fetchone()["created_at"]
        return Tag(id=tag_id, name=name, created_at=created_at)


def list_tags() -> list[Tag]:
    """List all tags ordered by name."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, created_at FROM tags ORDER BY name")
        return [Tag(id=row["id"], name=row["name"], created_at=row["created_at"]) for row in cursor.fetchall()]


def remove_tag(tag_name: str) -> bool:
    """Remove a tag by name. Unlinks from all articles via CASCADE. Returns True if removed."""
    with get_db() as conn:
        cursor = conn.cursor()
        # First get tag_id
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
        if not row:
            return False
        tag_id = row["id"]
        # Delete tag (article_tags cascade handled by FK)
        cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_tag_article_counts() -> dict[str, int]:
    """Returns {tag_name: item_count} for all tags.

    Counts articles that have each tag.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name, COUNT(at.article_id) as count
            FROM tags t
            LEFT JOIN article_tags at ON t.id = at.tag_id
            GROUP BY t.id, t.name
            ORDER BY t.name
        """)
        return {row["name"]: row["count"] for row in cursor.fetchall()}


def tag_article(article_id: str, tag_name: str) -> bool:
    """Link an article to a tag. Creates tag if it doesn't exist. Returns True if linked."""
    with get_db() as conn:
        cursor = conn.cursor()
        # Get or create tag
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
        if row:
            tag_id = row["id"]
        else:
            import uuid
            tag_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO tags (id, name) VALUES (?, ?)", (tag_id, tag_name))
            conn.commit()
        # Link article to tag
        try:
            cursor.execute(
                "INSERT INTO article_tags (article_id, tag_id) VALUES (?, ?)",
                (article_id, tag_id)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Already linked, not an error
            pass
        return True


def untag_article(article_id: str, tag_name: str) -> bool:
    """Remove link between article and tag. Returns True if unlinked."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
        if not row:
            return False
        tag_id = row["id"]
        cursor.execute(
            "DELETE FROM article_tags WHERE article_id = ? AND tag_id = ?",
            (article_id, tag_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_article_tags(article_id: str) -> list[str]:
    """Returns list of tag names for an article."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name FROM tags t
            JOIN article_tags at ON t.id = at.tag_id
            WHERE at.article_id = ?
            ORDER BY t.name
        """, (article_id,))
        return [row["name"] for row in cursor.fetchall()]


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
    import uuid
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
            article_id = str(uuid.uuid4())
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
