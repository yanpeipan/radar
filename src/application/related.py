"""Related articles business logic using ChromaDB semantic similarity."""

from __future__ import annotations

from src.application.articles import ArticleListItem
from src.storage.vector import get_related_articles as storage_get_related_articles


def get_related_articles(article_id: str, limit: int = 5) -> list[ArticleListItem]:
    """Get related articles as ArticleListItem objects.

    Args:
        article_id: The article ID to find related articles for.
        limit: Maximum number of related articles to return (default 5).

    Returns:
        List of ArticleListItem objects sorted by semantic similarity.
        Returns empty list if no related articles found or article has no embedding.
    """
    results = storage_get_related_articles(article_id=article_id, limit=limit)

    if not results:
        return []

    articles = []
    for result in results:
        sqlite_id = result.get("sqlite_id")
        if not sqlite_id:
            continue

        # Look up full article data from SQLite
        from src.storage.sqlite import get_article
        article = get_article(sqlite_id)
        if not article:
            continue

        distance = result.get("distance")
        score = max(0.0, 1.0 - distance * distance / 2.0) if distance is not None else 1.0

        articles.append(ArticleListItem(
            id=sqlite_id,
            feed_id=article.feed_id,
            feed_name=article.feed_name,
            title=result.get("title") or article.title,
            link=result.get("url") or article.link,
            guid=article.guid or sqlite_id,
            pub_date=article.pub_date,
            description=None,
            score=score,
        ))

    return articles
