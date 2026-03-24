"""Article operations for RSS reader.

Provides functions for listing and retrieving articles from the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.storage.sqlite import get_db


@dataclass
class ArticleListItem:
    """Represents an article with feed name for list display.

    Attributes:
        id: Unique identifier for the article.
        feed_id: ID of the feed this article belongs to.
        feed_name: Name of the feed.
        title: Title of the article.
        link: URL link to the full article.
        guid: Global unique identifier from the feed.
        pub_date: Publication date from the feed.
        description: Short description or summary.
    """

    id: str
    feed_id: str
    feed_name: str
    title: Optional[str]
    link: Optional[str]
    guid: str
    pub_date: Optional[str]
    description: Optional[str]


def list_articles(limit: int = 20, feed_id: Optional[str] = None) -> list[ArticleListItem]:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles to return (default 20).
        feed_id: Optional feed ID to filter articles by a specific feed.

    Returns:
        List of ArticleListItem objects ordered by pub_date DESC, limited to specified count.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        if feed_id:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.feed_id = ?
                ORDER BY a.pub_date DESC, a.created_at DESC
                LIMIT ?
                """,
                (feed_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                ORDER BY a.pub_date DESC, a.created_at DESC
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
                )
            )
        return articles


def get_article(article_id: str) -> Optional[ArticleListItem]:
    """Get a single article by ID.

    Args:
        article_id: The ID of the article to retrieve.

    Returns:
        ArticleListItem object if found, None otherwise.
    """
    with get_db() as conn:
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


def get_article_detail(article_id: str) -> Optional[dict]:
    """Get full article details including content and tags.

    Args:
        article_id: The ID of the article (can be truncated 8-char or full 32-char).

    Returns:
        Dict with all article fields plus 'tags' key containing list of tag names.
        Returns None if article not found.
    """
    with get_db() as conn:
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
        from src.storage.sqlite import get_article_tags
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


def search_articles(
    query: str,
    limit: int = 20,
    feed_id: Optional[str] = None
) -> list[ArticleListItem]:
    """Search articles using FTS5 full-text search.

    Args:
        query: FTS5 query string (space-separated = AND, use quotes for phrases)
        limit: Maximum number of results (default 20)
        feed_id: Optional feed ID to filter by specific feed

    Returns:
        List of ArticleListItem objects ordered by relevance
    """
    if not query or not query.strip():
        return []

    with get_db() as conn:
        cursor = conn.cursor()

        if feed_id:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
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
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE articles_fts MATCH ?
                ORDER BY bm25(articles_fts)
                LIMIT ?
                """,
                (query, limit),
            )

        articles = []
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
                )
            )

        return articles


def list_articles_with_tags(
    limit: int = 20,
    feed_id: Optional[str] = None,
    tag: Optional[str] = None,
    tags: Optional[str] = None
) -> list[ArticleListItem]:
    """List articles with optional tag filtering.

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

    if not tag_list:
        # No tag filter - use existing list_articles logic
        return list_articles(limit=limit, feed_id=feed_id)

    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(tag_list))

        if feed_id:
            cursor.execute(
                f"""
                SELECT DISTINCT a.id, a.feed_id,
                       f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
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
                """,
                [feed_id] + list(tag_list) + [limit],
            )
        else:
            cursor.execute(
                f"""
                SELECT DISTINCT a.id, a.feed_id,
                       f.name as feed_name,
                       a.title, a.link, a.guid, a.pub_date, a.description
                FROM articles a
                JOIN feeds f ON a.feed_id = f.id
                WHERE a.id IN (
                    SELECT DISTINCT at.article_id
                    FROM article_tags at
                    JOIN tags t ON at.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                )
                ORDER BY a.pub_date DESC, a.created_at DESC
                LIMIT ?
                """,
                list(tag_list) + [limit],
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
                )
            )
        return articles


def get_articles_with_tags(article_ids: list[str]) -> dict[str, list[str]]:
    """Batch fetch tags for multiple articles.

    Args:
        article_ids: List of article IDs to fetch tags for.

    Returns:
        Dict mapping article_id -> list of tag names.
    """
    result: dict[str, list[str]] = {aid: [] for aid in article_ids}

    if not article_ids:
        return result

    with get_db() as conn:
        cursor = conn.cursor()

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

        return result
