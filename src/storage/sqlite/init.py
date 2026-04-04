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
                    weight REAL DEFAULT 0.3,
                    "group" TEXT
                )
            """)

            # Migration: add group column to existing feeds table
            cursor.execute("PRAGMA table_info(feeds)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            if "group" not in existing_columns:
                cursor.execute('ALTER TABLE feeds ADD COLUMN "group" TEXT')
                logger.info("Migrated group column")

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
                    modified_at TEXT,
                    description TEXT,
                    content TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(feed_id, id)
                )
            """)

            # SQLite doesn't support ALTER COLUMN to change types, so skip the published_at migration
            # Check if author, tags, category columns exist before adding
            cursor.execute("PRAGMA table_info(articles)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in [
                ("author", "TEXT"),
                ("tags", "TEXT"),
                ("category", "TEXT"),
                ("meta", "TEXT"),
            ]:
                if col_name not in existing_columns:
                    cursor.execute(
                        f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}"
                    )
                    logger.info(f"Migrated {col_name} column")

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
            # Index for guid lookups (upsert, deduplication)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid)"
            )

            # Covering index for efficient feed article retrieval
            # Optimizes: SELECT * FROM articles WHERE feed_id = ? ORDER BY published_at DESC
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_feed_published ON articles(feed_id, published_at DESC)"
            )

            # FTS5 virtual table for full-text search
            # Uses porter tokenizer for English stemming
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    title,
                    description,
                    content,
                    author,
                    tags,
                    category,
                    tokenize='porter ascii'
                )
            """)

            conn.commit()
            logger.info("Database schema initialized")
