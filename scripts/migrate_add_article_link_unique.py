#!/usr/bin/env python3
"""Migration: Add UNIQUE constraint on articles.link, delete duplicate articles.

This script:
1. Counts and deletes duplicate articles (same link, keeping smallest rowid)
2. Creates a UNIQUE index on articles.link
3. Verifies the operation succeeded

Run: python scripts/migrate_add_article_link_unique.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import platformdirs


def get_db_path() -> str:
    """Return the database file path."""
    return str(
        Path(platformdirs.user_data_dir(appname="feedship", appauthor=False))
        / "feedship.db"
    )


def main() -> None:
    db_path = get_db_path()
    print(f"Database: {db_path}")

    # Check if DB exists
    if not Path(db_path).exists():
        print("ERROR: Database not found. Run 'feedship fetch' first.")
        return

    conn = sqlite3.connect(database=db_path)
    cursor = conn.cursor()

    # Count duplicates (same link, different rowid)
    cursor.execute("""
        SELECT COUNT(*) FROM articles
        WHERE link IS NOT NULL
        AND rowid NOT IN (
            SELECT MIN(rowid) FROM articles
            WHERE link IS NOT NULL
            GROUP BY link
        )
    """)
    duplicate_count = cursor.fetchone()[0]
    print(f"Found {duplicate_count} duplicate articles with same link")

    # Show total articles
    cursor.execute("SELECT COUNT(*) FROM articles")
    total_count = cursor.fetchone()[0]
    print(f"Total articles before migration: {total_count}")

    # Delete duplicates (keep smallest rowid per link group)
    if duplicate_count > 0:
        cursor.execute("""
            DELETE FROM articles
            WHERE link IS NOT NULL
            AND rowid NOT IN (
                SELECT MIN(rowid) FROM articles
                WHERE link IS NOT NULL
                GROUP BY link
            )
        """)
        deleted = cursor.rowcount
        conn.commit()
        print(f"Deleted {deleted} duplicate articles")
    else:
        print("No duplicates to delete")

    # Verify duplicates are gone
    cursor.execute("""
        SELECT COUNT(*) FROM articles
        WHERE link IS NOT NULL
        AND rowid NOT IN (
            SELECT MIN(rowid) FROM articles
            WHERE link IS NOT NULL
            GROUP BY link
        )
    """)
    remaining = cursor.fetchone()[0]
    print(f"Remaining duplicates after deletion: {remaining}")

    # Create UNIQUE index
    try:
        cursor.execute("CREATE UNIQUE INDEX idx_articles_link_unique ON articles(link)")
        conn.commit()
        print("Created UNIQUE index idx_articles_link_unique on articles.link")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("UNIQUE index already exists - skipping")
        else:
            raise

    # Final count
    cursor.execute("SELECT COUNT(*) FROM articles")
    final_count = cursor.fetchone()[0]
    print(f"Total articles after migration: {final_count}")
    print(f"Articles removed: {total_count - final_count}")

    conn.close()
    print("\nMigration complete!")


if __name__ == "__main__":
    main()
