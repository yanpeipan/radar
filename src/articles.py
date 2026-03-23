"""Article operations for RSS reader.

Provides functions for listing and retrieving articles from the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.db import get_connection


@dataclass
class ArticleListItem:
    """Represents an article with feed name for list display.

    Attributes:
        id: Unique identifier for the article.
        feed_id: ID of the feed this article belongs to (empty string for GitHub).
        feed_name: Name of the feed (from join) or GitHub repo name.
        title: Title of the article.
        link: URL link to the full article.
        guid: Global unique identifier from the feed.
        pub_date: Publication date from the feed.
        description: Short description or summary.
        source_type: Source type - "feed" or "github".
        repo_id: GitHub repo ID (only for github source_type).
        repo_name: GitHub repo name as "owner/repo" (only for github source_type).
        release_tag: Release tag version (only for github source_type).
    """

    id: str
    feed_id: str
    feed_name: str
    title: Optional[str]
    link: Optional[str]
    guid: str
    pub_date: Optional[str]
    description: Optional[str]
    source_type: str = "feed"
    repo_id: Optional[str] = None
    repo_name: Optional[str] = None
    release_tag: Optional[str] = None


def list_articles(limit: int = 20, feed_id: Optional[str] = None) -> list[ArticleListItem]:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles to return (default 20).
        feed_id: Optional feed ID to filter articles by a specific feed.
                 If provided, only feed articles are returned (GitHub releases
                 do not have a feed_id association).

    Returns:
        List of ArticleListItem objects ordered by pub_date DESC
        (or published_at DESC for GitHub releases), limited to specified count.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if feed_id:
            # When filtering by feed_id, only return feed articles
            cursor.execute(
                """
                SELECT 'feed' as source_type, a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description,
                       NULL as repo_id, NULL as repo_name, NULL as release_tag
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.feed_id = ?
                ORDER BY a.pub_date DESC, a.created_at DESC
                LIMIT ?
                """,
                (feed_id, limit),
            )
        else:
            # Return both feed articles and GitHub releases via UNION ALL
            cursor.execute(
                """
                SELECT 'feed' as source_type, a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description,
                       NULL as repo_id, NULL as repo_name, NULL as release_tag
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                UNION ALL
                SELECT 'github' as source_type, r.id, '' as feed_id,
                       g.owner || '/' || g.repo as feed_name,
                       COALESCE(r.name, r.tag_name) as title, r.html_url as link,
                       r.tag_name as guid, r.published_at as pub_date, r.body as description,
                       r.repo_id, g.name as repo_name, r.tag_name as release_tag
                FROM github_releases r
                JOIN github_repos g ON r.repo_id = g.id
                ORDER BY pub_date DESC
                LIMIT ?
                """,
                (limit,),
            )

        rows = cursor.fetchall()
        articles = []
        for row in rows:
            articles.append(
                ArticleListItem(
                    id=row["id"],
                    feed_id=row["feed_id"],
                    feed_name=row["feed_name"],
                    title=row["title"],
                    link=row["link"],
                    guid=row["guid"],
                    pub_date=row["pub_date"],
                    description=row["description"],
                    source_type=row["source_type"],
                    repo_id=row["repo_id"],
                    repo_name=row["repo_name"],
                    release_tag=row["release_tag"],
                )
            )
        return articles
    finally:
        conn.close()


def get_article(article_id: str) -> Optional[ArticleListItem]:
    """Get a single article by ID.

    Args:
        article_id: The ID of the article to retrieve.

    Returns:
        ArticleListItem object if found, None otherwise.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                   a.guid, a.pub_date, a.description
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.id = ?
            """,
            (article_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ArticleListItem(
            id=row["id"],
            feed_id=row["feed_id"],
            feed_name=row["feed_name"],
            title=row["title"],
            link=row["link"],
            guid=row["guid"],
            pub_date=row["pub_date"],
            description=row["description"],
        )
    finally:
        conn.close()


def get_article_detail(article_id: str) -> Optional[dict]:
    """Get full article details including content and tags.

    Args:
        article_id: The ID of the article (can be truncated 8-char or full 32-char).

    Returns:
        Dict with all article fields plus 'tags' key containing list of tag names.
        Returns None if article not found.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # First try exact match
        cursor.execute(
            """
            SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link, a.guid,
                   a.pub_date, a.description, a.content, 'feed' as source_type
            FROM articles a
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.id = ?
            """,
            (article_id,),
        )
        row = cursor.fetchone()

        # If not found and length == 8, try truncated ID match
        if not row and len(article_id) == 8:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link, a.guid,
                       a.pub_date, a.description, a.content, 'feed' as source_type
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.id LIKE ? || '%'
                LIMIT 1
                """,
                (article_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        # Fetch tags for the article
        from src.db import get_article_tags
        tags = get_article_tags(row["id"])

        return {
            "id": row["id"],
            "feed_id": row["feed_id"],
            "feed_name": row["feed_name"],
            "title": row["title"],
            "link": row["link"],
            "guid": row["guid"],
            "pub_date": row["pub_date"],
            "description": row["description"],
            "content": row["content"],
            "source_type": row["source_type"],
            "tags": tags,
        }
    finally:
        conn.close()


def search_articles(
    query: str,
    limit: int = 20,
    feed_id: Optional[str] = None
) -> list[ArticleListItem]:
    """Search articles using FTS5 full-text search and GitHub releases.

    Args:
        query: FTS5 query string (space-separated = AND, use quotes for phrases)
        limit: Maximum number of results (default 20)
        feed_id: Optional feed ID to filter by specific feed

    Returns:
        List of ArticleListItem objects ordered by relevance
    """
    if not query or not query.strip():
        return []

    conn = get_connection()
    try:
        cursor = conn.cursor()
        articles = []

        # FTS5 MATCH for feed articles with bm25 ranking
        if feed_id:
            cursor.execute(
                """
                SELECT 'feed' as source_type, a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description,
                       NULL as repo_id, NULL as repo_name, NULL as release_tag
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE articles_fts MATCH ?
                  AND a.feed_id = ?
                ORDER BY bm25(articles_fts)
                LIMIT ?
                """,
                (query, feed_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT 'feed' as source_type, a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description,
                       NULL as repo_id, NULL as repo_name, NULL as release_tag
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE articles_fts MATCH ?
                ORDER BY bm25(articles_fts)
                LIMIT ?
                """,
                (query, limit),
            )

        for row in cursor.fetchall():
            articles.append(
                ArticleListItem(
                    id=row["id"],
                    feed_id=row["feed_id"],
                    feed_name=row["feed_name"],
                    title=row["title"],
                    link=row["link"],
                    guid=row["guid"],
                    pub_date=row["pub_date"],
                    description=row["description"],
                    source_type=row["source_type"],
                    repo_id=row["repo_id"],
                    repo_name=row["repo_name"],
                    release_tag=row["release_tag"],
                )
            )

        # If no feed_id filter, also search GitHub releases via LIKE
        # (github_releases.body is not in FTS5, so we use LIKE for searching)
        if not feed_id:
            like_query = f'%{query}%'
            cursor.execute(
                """
                SELECT 'github' as source_type, r.id, '' as feed_id,
                       g.owner || '/' || g.repo as feed_name,
                       COALESCE(r.name, r.tag_name) as title, r.html_url as link,
                       r.tag_name as guid, r.published_at as pub_date, r.body as description,
                       r.repo_id, g.name as repo_name, r.tag_name as release_tag
                FROM github_releases r
                JOIN github_repos g ON r.repo_id = g.id
                WHERE r.tag_name LIKE ? OR r.name LIKE ? OR r.body LIKE ?
                LIMIT ?
                """,
                (like_query, like_query, like_query, limit),
            )

            for row in cursor.fetchall():
                articles.append(
                    ArticleListItem(
                        id=row["id"],
                        feed_id=row["feed_id"],
                        feed_name=row["feed_name"],
                        title=row["title"],
                        link=row["link"],
                        guid=row["guid"],
                        pub_date=row["pub_date"],
                        description=row["description"],
                        source_type=row["source_type"],
                        repo_id=row["repo_id"],
                        repo_name=row["repo_name"],
                        release_tag=row["release_tag"],
                    )
                )

        return articles
    finally:
        conn.close()


def list_articles_with_tags(
    limit: int = 20,
    feed_id: Optional[str] = None,
    tag: Optional[str] = None,
    tags: Optional[str] = None
) -> list[ArticleListItem]:
    """List articles with optional tag filtering (D-14, D-15).

    Args:
        limit: Maximum number of articles.
        feed_id: Filter by feed ID.
        tag: Single tag name filter (must have).
        tags: Comma-separated tag names (OR logic - has a OR has b).
              If both tag and tags provided, tag takes precedence.
    """
    # Parse multiple tags
    tag_list: Optional[list[str]] = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif tag:
        tag_list = [tag]

    conn = get_connection()
    try:
        cursor = conn.cursor()

        if not tag_list:
            # No tag filter - use existing list_articles logic
            return list_articles(limit=limit, feed_id=feed_id)

        # Build query with tag filter - includes BOTH feed articles AND GitHub releases
        placeholders = ",".join("?" * len(tag_list))

        if feed_id:
            # When filtering by feed_id, only return feed articles (no releases)
            sql = f"""
                SELECT DISTINCT a.id, a.feed_id,
                       f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description,
                       'feed' as source_type,
                       CAST(NULL AS TEXT) as repo_id, CAST(NULL AS TEXT) as repo_name, CAST(NULL AS TEXT) as release_tag
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.feed_id = ?
                  AND a.id IN (
                      SELECT DISTINCT at.article_id
                      FROM article_tags at
                      JOIN tags t ON at.tag_id = t.id
                      WHERE t.name IN ({placeholders})
                  )
                ORDER BY a.pub_date DESC, a.created_at DESC
                LIMIT ?
            """
            params = [feed_id] + list(tag_list) + [limit]
        else:
            # Return both feed articles AND GitHub releases with matching tags
            sql = f"""
                SELECT 'feed' as source_type, a.id, a.feed_id,
                       COALESCE(f.name, '') as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description,
                       CAST(NULL AS TEXT) as repo_id, CAST(NULL AS TEXT) as repo_name, CAST(NULL AS TEXT) as release_tag
                FROM articles a
                LEFT JOIN feeds f ON a.feed_id = f.id
                WHERE a.id IN (
                    SELECT DISTINCT at.article_id
                    FROM article_tags at
                    JOIN tags t ON at.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                )
                UNION ALL
                SELECT 'github' as source_type, r.id, '' as feed_id,
                       g.owner || '/' || g.repo as feed_name,
                       COALESCE(r.name, r.tag_name) as title, r.html_url as link,
                       r.tag_name as guid, r.published_at as pub_date, r.body as description,
                       r.repo_id, g.name as repo_name, r.tag_name as release_tag
                FROM github_releases r
                JOIN github_repos g ON r.repo_id = g.id
                WHERE r.id IN (
                    SELECT DISTINCT grt.release_id
                    FROM github_release_tags grt
                    JOIN tags t ON grt.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                )
                ORDER BY pub_date DESC
                LIMIT ?
            """
            params = list(tag_list) + list(tag_list) + [limit]

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        articles = []
        for row in rows:
            articles.append(
                ArticleListItem(
                    id=row["id"],
                    feed_id=row["feed_id"],
                    feed_name=row["feed_name"],
                    title=row["title"],
                    link=row["link"],
                    guid=row["guid"],
                    pub_date=row["pub_date"],
                    description=row["description"],
                    source_type=row["source_type"],
                    repo_id=row["repo_id"] if row["repo_id"] else None,
                    repo_name=row["repo_name"] if row["repo_name"] else None,
                    release_tag=row["release_tag"],
                )
            )
        return articles
    finally:
        conn.close()


def get_articles_with_tags(article_ids: list[str], release_ids: Optional[list[str]] = None) -> dict[str, list[str]]:
    """Batch fetch tags for multiple articles and optionally releases.

    Args:
        article_ids: List of article IDs to fetch tags for.
        release_ids: List of release IDs to fetch tags for.

    Returns:
        Dict mapping article_id -> list of tag names, and release_id -> list of tag names.
    """
    result: dict[str, list[str]] = {aid: [] for aid in article_ids}
    if release_ids:
        result.update({rid: [] for rid in release_ids})

    if not article_ids and not release_ids:
        return result

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Fetch article tags
        if article_ids:
            placeholders = ",".join("?" * len(article_ids))
            cursor.execute(f"""
                SELECT at.article_id, t.name
                FROM article_tags at
                JOIN tags t ON at.tag_id = t.id
                WHERE at.article_id IN ({placeholders})
                ORDER BY at.article_id, t.name
            """, article_ids)

            for row in cursor.fetchall():
                result[row["article_id"]].append(row["name"])

        # Fetch release tags
        if release_ids:
            placeholders = ",".join("?" * len(release_ids))
            cursor.execute(f"""
                SELECT grt.release_id, t.name
                FROM github_release_tags grt
                JOIN tags t ON grt.tag_id = t.id
                WHERE grt.release_id IN ({placeholders})
                ORDER BY grt.release_id, t.name
            """, release_ids)

            for row in cursor.fetchall():
                result[row["release_id"]].append(row["name"])

        return result
    finally:
        conn.close()
