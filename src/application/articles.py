"""Article operations for RSS reader.

Provides functions for listing and retrieving articles from the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.storage import (
    list_articles as storage_list_articles,
    get_article as storage_get_article,
    get_article_detail as storage_get_article_detail,
    search_articles as storage_search_articles,
)


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
    return storage_list_articles(limit=limit, feed_id=feed_id)


def get_article(article_id: str) -> Optional[ArticleListItem]:
    """Get a single article by ID.

    Args:
        article_id: The ID of the article to retrieve.

    Returns:
        ArticleListItem object if found, None otherwise.
    """
    return storage_get_article(article_id)


def get_article_detail(article_id: str) -> Optional[dict]:
    """Get full article details including content.

    Args:
        article_id: The ID of the article (can be truncated 8-char or full 32-char).

    Returns:
        Dict with all article fields.
        Returns None if article not found.
    """
    return storage_get_article_detail(article_id)


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
    return storage_search_articles(query=query, limit=limit, feed_id=feed_id)
