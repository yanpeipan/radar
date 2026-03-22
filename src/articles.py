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
        feed_id: ID of the feed this article belongs to.
        feed_name: Name of the feed (from join).
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
        List of ArticleListItem objects ordered by pub_date DESC
        (or created_at DESC if no pub_date), limited to specified count.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if feed_id:
            cursor.execute(
                """
                SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                       a.guid, a.pub_date, a.description
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
                SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
                       a.guid, a.pub_date, a.description
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
