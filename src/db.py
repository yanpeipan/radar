"""Database module for RSS reader.

Provides SQLite database connection with WAL mode and schema initialization.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

import platformdirs

if TYPE_CHECKING:
    from typing import Iterator


# Import Tag here since it's used at runtime in CRUD functions
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

        # GitHub release tags table (many-to-many)
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_github_release_tags_tag_id ON github_release_tags(tag_id)")

        # Add repo_id column for GitHub changelog association (Phase 5)
        # This is a migration-safe check - only add if column doesn't exist
        cursor.execute("PRAGMA table_info(articles)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'repo_id' not in columns:
            cursor.execute("ALTER TABLE articles ADD COLUMN repo_id TEXT REFERENCES github_repos(id) ON DELETE SET NULL")

        conn.commit()

        # Run v1.3 migrations after schema creation
        try:
            from src.db_migrations import run_v13_migrations
            migration_results = run_v13_migrations()
            logger.info("v1.3 migrations completed: %s", migration_results)
        except Exception:
            # Log but don't fail init if migrations fail (database might be read-only)
            logger.exception("Failed to run v1.3 migrations")
    finally:
        conn.close()


def add_tag(name: str) -> Tag:
    """Create a new tag. Returns Tag object."""
    import uuid
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def list_tags() -> list[Tag]:
    """List all tags ordered by name."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, created_at FROM tags ORDER BY name")
        return [Tag(id=row["id"], name=row["name"], created_at=row["created_at"]) for row in cursor.fetchall()]
    finally:
        conn.close()


def remove_tag(tag_name: str) -> bool:
    """Remove a tag by name. Unlinks from all articles via CASCADE. Returns True if removed."""
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def get_tag_article_counts() -> dict[str, int]:
    """Returns {tag_name: item_count} for all tags.

    Counts both feed articles AND GitHub releases that have each tag.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name, (
                SELECT COUNT(*) FROM article_tags at WHERE at.tag_id = t.id
                UNION ALL
                SELECT COUNT(*) FROM github_release_tags grt WHERE grt.tag_id = t.id
            ) as count
            FROM tags t
            GROUP BY t.id, t.name
            ORDER BY t.name
        """)
        return {row["name"]: row["count"] for row in cursor.fetchall()}
    finally:
        conn.close()


def tag_article(article_id: str, tag_name: str) -> bool:
    """Link an article to a tag. Creates tag if it doesn't exist. Returns True if linked."""
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def untag_article(article_id: str, tag_name: str) -> bool:
    """Remove link between article and tag. Returns True if unlinked."""
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def tag_github_release(release_id: str, tag_name: str) -> bool:
    """Link a GitHub release to a tag. Creates tag if it doesn't exist. Returns True if linked."""
    conn = get_connection()
    try:
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
        # Link release to tag
        try:
            cursor.execute(
                "INSERT INTO github_release_tags (release_id, tag_id) VALUES (?, ?)",
                (release_id, tag_id)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Already linked, not an error
            pass
        return True
    finally:
        conn.close()


def untag_github_release(release_id: str, tag_name: str) -> bool:
    """Remove link between GitHub release and tag. Returns True if unlinked."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
        if not row:
            return False
        tag_id = row["id"]
        cursor.execute(
            "DELETE FROM github_release_tags WHERE release_id = ? AND tag_id = ?",
            (release_id, tag_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_release_tags(release_id: str) -> list[str]:
    """Returns list of tag names for a GitHub release."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name FROM tags t
            JOIN github_release_tags grt ON t.id = grt.tag_id
            WHERE grt.release_id = ?
            ORDER BY t.name
        """, (release_id,))
        return [row["name"] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_release_detail(release_id: str) -> Optional[dict]:
    """Get full GitHub release details including tags.

    Args:
        release_id: The ID of the release (can be truncated 8-char or full 32-char).

    Returns:
        Dict with all release fields plus 'tags' key containing list of tag names.
        Returns None if release not found.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # First try exact match
        cursor.execute("""
            SELECT r.*, g.name as repo_name, g.owner, g.repo
            FROM github_releases r
            JOIN github_repos g ON r.repo_id = g.id
            WHERE r.id = ?
        """, (release_id,))
        row = cursor.fetchone()

        # If not found and length == 8, try truncated ID match
        if not row and len(release_id) == 8:
            cursor.execute("""
                SELECT r.*, g.name as repo_name, g.owner, g.repo
                FROM github_releases r
                JOIN github_repos g ON r.repo_id = g.id
                WHERE r.id LIKE ? || '%'
                LIMIT 1
            """, (release_id,))
            row = cursor.fetchone()

        if not row:
            return None

        # Fetch tags for the release
        tags = get_release_tags(row["id"])

        return {
            "id": row["id"],
            "repo_id": row["repo_id"],
            "repo_name": row["repo_name"],
            "tag_name": row["tag_name"],
            "name": row["name"],
            "body": row["body"],
            "html_url": row["html_url"],
            "published_at": row["published_at"],
            "created_at": row["created_at"],
            "tags": tags,
        }
    finally:
        conn.close()


def get_article_tags(article_id: str) -> list[str]:
    """Returns list of tag names for an article."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name FROM tags t
            JOIN article_tags at ON t.id = at.tag_id
            WHERE at.article_id = ?
            ORDER BY t.name
        """, (article_id,))
        return [row["name"] for row in cursor.fetchall()]
    finally:
        conn.close()


def store_article(
    guid: str,
    title: str,
    content: str,
    link: str,
    feed_id: Optional[str] = None,
    repo_id: Optional[str] = None,
    pub_date: Optional[str] = None,
) -> str:
    """Store an article (insert or update based on guid existence).

    Args:
        guid: Unique identifier for the article.
        title: Article title.
        content: Article content (markdown/html).
        link: URL to the article.
        feed_id: Feed ID if from RSS feed (optional).
        repo_id: GitHub repo ID if from GitHub source (optional).
        pub_date: Publication date (optional).

    Returns:
        Article ID (existing if updated, new if inserted).
    """
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
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
                """INSERT INTO articles (id, feed_id, repo_id, title, link, guid, pub_date, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article_id,
                    feed_id or "",
                    repo_id or None,
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
    finally:
        conn.close()
