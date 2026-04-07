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
                    "group" TEXT
                )
            """)

            cursor.execute("PRAGMA table_info(feeds)")
            if "group" not in {row[1] for row in cursor.fetchall()}:
                cursor.execute('ALTER TABLE feeds ADD COLUMN "group" TEXT')
                logger.debug("Migrated group column")

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
