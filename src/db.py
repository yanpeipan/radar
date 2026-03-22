"""Database module for RSS reader.

Provides SQLite database connection with WAL mode and schema initialization.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import platformdirs

if TYPE_CHECKING:
    from typing import Iterator


# Cross-platform database path using platformdirs
_DB_DIR = platformdirs.user_data_dir(appname="rss-reader", appauthor=False)
_DB_PATH = Path(_DB_DIR) / "rss-reader.db"


def get_db_path() -> str:
    """Return the database file path as a string.

    Returns:
        Absolute path to the SQLite database file.
    """
    return str(_DB_PATH)


def get_connection() -> sqlite3.Connection:
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


def init_db() -> None:
    """Initialize the database schema.

    Creates the feeds table and articles table with appropriate indexes
    if they do not already exist.

    Feeds table stores feed sources with metadata for conditional fetching.
    Articles table stores individual items with foreign key to feeds.
    """
    conn = get_connection()
    try:
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                title TEXT,
                link TEXT,
                guid TEXT NOT NULL,
                pub_date TEXT,
                description TEXT,
                content TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(feed_id, guid)
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

        # GitHub repositories table: stores monitored GitHub repositories
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

        # GitHub releases table: stores release information
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

        # Indexes for GitHub tables
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_github_releases_repo_id ON github_releases(repo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_github_releases_published ON github_releases(published_at)")

        conn.commit()
    finally:
        conn.close()
