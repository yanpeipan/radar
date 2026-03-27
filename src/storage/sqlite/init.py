"""Database schema initialization."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handles database schema creation and initialization."""

    def init_db(self) -> None:
        """Initialize the database schema.

        Creates all tables and indexes if they do not already exist.
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
                    last_modified TEXT,
                    last_fetched TEXT,
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
                    pub_date TEXT,
                    description TEXT,
                    content TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    repo_id TEXT REFERENCES github_repos(id) ON DELETE SET NULL,
                    UNIQUE(feed_id, id)
                )
            """)

            # Indexes for common query patterns
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_pub_date ON articles(pub_date)"
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

            # Tags table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Article-Tags junction table
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

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_article_tags_tag_id ON article_tags(tag_id)"
            )

            # GitHub repos table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS github_repos (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    repo TEXT NOT NULL,
                    last_fetched TEXT,
                    last_tag TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(owner, repo)
                )
            """)

            # GitHub releases table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS github_releases (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT NOT NULL REFERENCES github_repos(id) ON DELETE CASCADE,
                    tag_name TEXT NOT NULL,
                    name TEXT,
                    body TEXT,
                    html_url TEXT NOT NULL,
                    published_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo_id, tag_name)
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_github_releases_repo_id ON github_releases(repo_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_github_releases_published ON github_releases(published_at)"
            )

            # GitHub release tags junction table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS github_release_tags (
                    release_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (release_id, tag_id),
                    FOREIGN KEY (release_id) REFERENCES github_releases(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_github_release_tags_tag_id ON github_release_tags(tag_id)"
            )

            # Article embeddings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS article_embeddings (
                    article_id TEXT PRIMARY KEY,
                    embedding BLOB
                )
            """)

            conn.commit()
            logger.info("Database schema initialized")
