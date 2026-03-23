"""Database migrations for v1.3 provider architecture.

Provides migration functions for:
- DB-01: Adding metadata TEXT column to feeds table
- DB-02: Migrating github_repos data to feeds.metadata JSON
- DB-03: Dropping github_repos table (after DB-02 migration)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from src.db import get_connection

logger = logging.getLogger(__name__)


def migrate_feeds_metadata_column() -> bool:
    """Add metadata TEXT column to feeds table if it doesn't exist.

    This column stores JSON with provider-specific data like github_token.

    Returns:
        True if column was added or already exists.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Check if column exists using PRAGMA table_info
        cursor.execute("PRAGMA table_info(feeds)")
        columns = [row[1] for row in cursor.fetchall()]

        if "metadata" not in columns:
            cursor.execute("ALTER TABLE feeds ADD COLUMN metadata TEXT")
            conn.commit()
            logger.info("Added metadata column to feeds table")
            return True
        else:
            logger.debug("metadata column already exists")
            return True
    finally:
        conn.close()


def migrate_github_repos_to_feeds() -> int:
    """Migrate github_repos data to feeds.metadata JSON.

    For each github_repos row:
    - If corresponding feeds row exists (by owner/repo URL): update feeds.metadata
    - If no corresponding feeds row: create feeds row with metadata

    The metadata JSON contains: owner, repo, github_token

    Returns:
        Number of github_repos rows processed.
    """
    conn = get_connection()
    migrated = 0

    try:
        cursor = conn.cursor()

        # Check if github_repos table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='github_repos'"
        )
        if not cursor.fetchone():
            logger.debug("github_repos table doesn't exist, nothing to migrate")
            return 0

        # Get all github_repos rows
        cursor.execute("SELECT * FROM github_repos")
        repos = cursor.fetchall()

        for repo in repos:
            repo_id = repo["id"]
            owner = repo["owner"]
            repo_name = repo["repo"]
            # The 'name' field in github_repos stores display name (owner/repo format)
            # Not the actual GitHub token - tokens are stored in environment
            # We store metadata for future provider use

            # Build GitHub URL for matching
            github_url = f"https://github.com/{owner}/{repo_name}"

            # Check if feeds row exists for this URL
            cursor.execute("SELECT id, metadata FROM feeds WHERE url = ?", (github_url,))
            existing_feed = cursor.fetchone()

            # Prepare metadata JSON
            metadata = {
                "owner": owner,
                "repo": repo_name,
                "source": "github_repos_migration",
            }

            if existing_feed:
                # Update existing feeds row with metadata
                existing_metadata = {}
                if existing_feed["metadata"]:
                    try:
                        existing_metadata = json.loads(existing_feed["metadata"])
                    except json.JSONDecodeError:
                        pass
                # Merge metadata (new values override)
                existing_metadata.update(metadata)
                cursor.execute(
                    "UPDATE feeds SET metadata = ? WHERE id = ?",
                    (json.dumps(existing_metadata), existing_feed["id"])
                )
                logger.debug("Updated feeds.metadata for %s", github_url)
            else:
                # Create new feeds row
                import uuid
                from datetime import datetime, timezone

                feed_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                display_name = f"{owner}/{repo_name}"

                cursor.execute(
                    """INSERT INTO feeds (id, name, url, metadata, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (feed_id, display_name, github_url, json.dumps(metadata), now)
                )
                logger.debug("Created feeds row for %s", github_url)

            migrated += 1

        conn.commit()
        logger.info("Migrated %d github_repos rows to feeds.metadata", migrated)
        return migrated
    finally:
        conn.close()


def migrate_drop_github_repos() -> bool:
    """Drop github_repos table after successful migration.

    Returns:
        True if table was dropped or didn't exist.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='github_repos'"
        )
        if not cursor.fetchone():
            logger.debug("github_repos table doesn't exist, nothing to drop")
            return True

        cursor.execute("DROP TABLE github_repos")
        conn.commit()
        logger.info("Dropped github_repos table")
        return True
    except Exception:
        logger.exception("Failed to drop github_repos table")
        return False
    finally:
        conn.close()


def run_v13_migrations() -> dict:
    """Run all v1.3 provider architecture migrations.

    This is the main entry point called by init_db().

    Returns:
        Dict with migration results: {
            "metadata_column_added": bool,
            "github_repos_migrated": int,
            "github_repos_dropped": bool
        }
    """
    results = {
        "metadata_column_added": False,
        "github_repos_migrated": 0,
        "github_repos_dropped": False,
    }

    # DB-01: Add metadata column
    results["metadata_column_added"] = migrate_feeds_metadata_column()

    # DB-02: Migrate github_repos data
    results["github_repos_migrated"] = migrate_github_repos_to_feeds()

    # DB-03: Drop github_repos table (only if we migrated something)
    if results["github_repos_migrated"] > 0:
        results["github_repos_dropped"] = migrate_drop_github_repos()

    return results
