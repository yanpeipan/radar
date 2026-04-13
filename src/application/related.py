"""Related articles business logic using ChromaDB semantic similarity."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from src.application.articles import ArticleListItem
from src.storage.vector import get_related_articles as storage_get_related_articles

if TYPE_CHECKING:
    pass


@lru_cache
def _check_ml_dependencies():
    """Lazy check that ML dependencies (sentence-transformers, chromadb) are available.

    Raises:
        RuntimeError: If sentence-transformers or chromadb cannot be imported.
    """
    try:
        import chromadb  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "ChromaDB is required for related articles. "
            "Install with: pip install chromadb"
        ) from e

    try:
        import sentence_transformers  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "sentence-transformers is required for related articles. "
            "Install with: pip install sentence-transformers"
        ) from e


def get_related_articles(article_id: str, limit: int = 5) -> list[ArticleListItem]:
    """Get related articles as ArticleListItem objects.

    Args:
        article_id: The article ID to find related articles for.
        limit: Maximum number of related articles to return (default 5).

    Returns:
        List of ArticleListItem objects sorted by semantic similarity.
        Returns empty list if no related articles found or article has no embedding.
    """
    _check_ml_dependencies()
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
        score = (
            max(0.0, 1.0 - distance * distance / 2.0) if distance is not None else 1.0
        )

        articles.append(
            ArticleListItem(
                id=sqlite_id,
                feed_id=article.feed_id,
                feed_name=article.feed_name,
                title=result.get("title") or article.title,
                link=result.get("url") or article.link,
                guid=article.guid or sqlite_id,
                published_at=article.published_at,
                description=None,
                score=score,
            )
        )

    return articles
