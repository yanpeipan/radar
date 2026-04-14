"""Database schema initialization."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Articles table base columns
_ARTICLES_BASE = """\
    id TEXT NOT NULL,
    feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    title TEXT,
    link TEXT,
    guid TEXT NOT NULL,
    published_at TEXT,
    modified_at TEXT,
    description TEXT,
    content TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP"""

# Columns added over the base schema
_ARTICLES_EXTRA_COLUMNS = {
    "author": "TEXT",
    "tags": "TEXT",
    "category": "TEXT",
    "meta": "TEXT",
    # LLM fields (v1.11)
    "summary": "TEXT",
    "quality_score": "REAL",
    "keywords": "TEXT",  # JSON array
    "summarized_at": "TEXT",  # ISO timestamp
    # Dedup fields (v1.12)
    "content_hash": "TEXT",  # SHA256 of title + first 500 chars
    "minhash_signature": "BLOB",  # Pickled MinHash signature
}


class DatabaseInitializer:
    """Handles database schema creation and initialization."""

    def init_db(self) -> None:
        """Initialize the database schema.

        Creates the feeds table and articles table with appropriate indexes
        if they do not already exist.
        """
        from src.storage.sqlite import get_db

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feeds (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    etag TEXT,
                    modified_at TEXT,
                    fetched_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    weight REAL DEFAULT 0.3,
                    "group" TEXT,
                    refresh_interval INTEGER DEFAULT 3600
                )
            """)

            cursor.execute("PRAGMA table_info(feeds)")
            if "group" not in {row[1] for row in cursor.fetchall()}:
                cursor.execute('ALTER TABLE feeds ADD COLUMN "group" TEXT')
                logger.debug("Migrated group column")

            cursor.execute("PRAGMA table_info(feeds)")
            if "refresh_interval" not in {row[1] for row in cursor.fetchall()}:
                cursor.execute(
                    "ALTER TABLE feeds ADD COLUMN refresh_interval INTEGER DEFAULT 3600"
                )
                logger.debug("Migrated refresh_interval column")

            extra_cols = "".join(
                f"\n    {name} {typ}," for name, typ in _ARTICLES_EXTRA_COLUMNS.items()
            )
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS articles (
                    {_ARTICLES_BASE},
                    {extra_cols}
                    UNIQUE(feed_id, guid)
                )
            """)

            # Add any missing columns (forward-compatibility for existing dbs)
            cursor.execute("PRAGMA table_info(articles)")
            existing = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in _ARTICLES_EXTRA_COLUMNS.items():
                if col_name not in existing:
                    cursor.execute(
                        f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}"
                    )
                    logger.debug(f"Migrated {col_name} column")

            # Indexes
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id)",
                "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
                "CREATE INDEX IF NOT EXISTS idx_articles_link ON articles(link)",
                "CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid)",
                "CREATE INDEX IF NOT EXISTS idx_articles_feed_published ON articles(feed_id, published_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash)",
            ):
                cursor.execute(idx_sql)

            # Tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)

            # Feed tags join table (many-to-many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feed_tags (
                    feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                    tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (feed_id, tag_id)
                )
            """)

            # Index for fast tag-to-feed lookup
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_feed_tags_tag_id ON feed_tags(tag_id)",
            ):
                cursor.execute(idx_sql)

            # FTS5 virtual table for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    title, description, content, author, tags, category,
                    tokenize='porter ascii'
                )
            """)

            conn.commit()
            logger.info("Database schema initialized")
