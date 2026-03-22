"""Article operations for RSS reader.

Provides functions for listing and retrieving articles from the database.
"""

from __future__ import annotations

from dataclasses import dataclass
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
                ORDER BY pub_date DESC, created_at DESC
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
        List of ArticleListItem objects ordered by bm25 relevance
    """
    if not query or not query.strip():
        return []

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # FTS5 MATCH with bm25 ranking
        if feed_id:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                       a.guid, a.pub_date, a.description
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.id
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
                SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                       a.guid, a.pub_date, a.description
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.id
                JOIN feeds f ON a.feed_id = f.id
                WHERE articles_fts MATCH ?
                ORDER BY bm25(articles_fts)
                LIMIT ?
                """,
                (query, limit),
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
    finally:
        conn.close()
