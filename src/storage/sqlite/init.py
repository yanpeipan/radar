"""Database schema initialization."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database schema creation and initialization."""

    def init_db(self) -> None:
        """Initialize the database schema.

        Creates the feeds table and articles table with appropriate indexes
        if they do not already exist.

        Feeds table stores feed sources with metadata for conditional fetching.
        Articles table stores individual items with foreign key to feeds.
        """
        from src.storage.sqlite import get_db

        with get_db() as conn:
            cursor = conn.cursor()

            # Feeds table: stores RSS/Atom feed sources
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
                    published_at TEXT,
                    modified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    content TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(feed_id, id)
                )
            """)

            # Migrate pub_date to published_at TEXT (SQLite supports ALTER COLUMN in 3.25.0+)
            # Using try/except because column type change only applies if column was previously TEXT
            try:
                cursor.execute("ALTER TABLE articles ALTER COLUMN published_at TEXT")
                logger.info("Migrated published_at column")
            except Exception as e:
                # Column may already be INTEGER or other error - safe to ignore
                logger.debug(f"pub_date column migration skipped: {e}")

            # Indexes for common query patterns
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_link ON articles(link)"
            )

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
            logger.info("Database schema initialized")
