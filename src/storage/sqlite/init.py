"""Database schema initialization."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Articles table base columns (without migration additions)
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

# Columns added by the UNIQUE(feed_id, guid) migration
_ARTICLES_MIGRATION_ADDITIONS = {
    "author": "TEXT",
    "tags": "TEXT",
    "category": "TEXT",
    "meta": "TEXT",
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

            # Feeds table
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

            # Articles table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS articles (
                    {_ARTICLES_BASE},
                    UNIQUE(feed_id, guid)
                )
            """)

            # Migration: UNIQUE(feed_id, id) -> UNIQUE(feed_id, guid)
            cursor.execute("PRAGMA index_list(articles)")
            indexes = [row[1] for row in cursor.fetchall()]
            has_old = any(
                "articles_feed_id_id" in idx
                or idx.startswith("sqlite_autoindex_articles_")
                for idx in indexes
            )
            has_new = any("articles_feed_id_guid" in idx for idx in indexes)

            if has_old and not has_new:
                logger.debug(
                    "Migrating articles table: changing UNIQUE(feed_id, id) to UNIQUE(feed_id, guid)"
                )
                cursor.execute("DROP TABLE IF EXISTS articles_new")
                migration_cols = "\n".join(
                    f"    {name} {typ},"
                    for name, typ in _ARTICLES_MIGRATION_ADDITIONS.items()
                )
                cursor.execute(f"""
                    CREATE TABLE articles_new (
                        {_ARTICLES_BASE},
                        {migration_cols}
                        UNIQUE(feed_id, guid)
                    )
                """)
                # Deduplicate: keep row with latest modified_at per (feed_id, guid),
                # tie-break by highest id
                cursor.execute("""
                    INSERT INTO articles_new
                    SELECT a.* FROM articles a
                    INNER JOIN (
                        SELECT feed_id, guid, modified_at,
                               ROW_NUMBER() OVER (
                                   PARTITION BY feed_id, guid
                                   ORDER BY modified_at DESC, id DESC
                               ) as rn
                        FROM articles
                    ) b ON a.feed_id = b.feed_id AND a.guid = b.guid
                        AND a.modified_at = b.modified_at AND b.rn = 1
                """)
                cursor.execute("DROP TABLE articles")
                cursor.execute("ALTER TABLE articles_new RENAME TO articles")
                logger.debug("Migration complete")

            # Add missing columns (works on both migrated and non-migrated schemas)
            cursor.execute("PRAGMA table_info(articles)")
            existing = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in _ARTICLES_MIGRATION_ADDITIONS.items():
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
