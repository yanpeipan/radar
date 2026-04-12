"""Article operations for RSS reader.

Provides functions for listing and retrieving articles from the database.
Scoring and ranking logic is encapsulated in this layer.
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass

from src.application.combine import combine_scores
from src.storage import (
    get_article as storage_get_article,
)
from src.storage import (
    get_article_detail as storage_get_article_detail,
)
from src.storage import (
    list_articles as storage_list_articles,
)
from src.storage import (
    search_articles_fts as storage_search_articles_fts,
)
from src.storage.vector import (
    search_articles_semantic as storage_search_articles_semantic,
)

logger = logging.getLogger(__name__)


def _check_ml_dependencies() -> bool:
    """Check whether optional ML dependencies (chromadb, sentence-transformers) are available.

    Returns:
        True if all ML dependencies are installed.

    Raises:
        RuntimeError: If any ML dependency is missing, with an install hint.
    """
    try:
        import chromadb  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "Semantic search requires chromadb and sentence-transformers. "
            "Install with: pip install feedship[ml]"
        ) from e
    return True


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
        published_at: Publication date from the feed.
        description: Short description or summary.
    """

    id: str
    feed_id: str
    feed_name: str
    title: str | None
    link: str | None
    guid: str
    published_at: str | None
    description: str | None
    vec_sim: float = 0.0
    bm25_score: float = 0.0
    freshness: float = 0.0
    source_weight: float = 0.3
    ce_score: float = 0.0
    score: float = 0.0
    quality_score: float | None = None
    content: str | None = None
    summary: str | None = None
    feed_weight: float | None = None
    feed_url: str | None = None
    content_hash: str | None = None
    minhash_signature: bytes | None = None
    tags: list[str] = []
    translation: str | None = None

    def to_dict(self) -> dict:
        """Convert to dict for boundaries that require dict (e.g., template rendering)."""
        return {
            "id": self.id,
            "feed_id": self.feed_id,
            "feed_name": self.feed_name,
            "title": self.title,
            "link": self.link,
            "guid": self.guid,
            "published_at": self.published_at,
            "description": self.description,
            "vec_sim": self.vec_sim,
            "bm25_score": self.bm25_score,
            "freshness": self.freshness,
            "source_weight": self.source_weight,
            "ce_score": self.ce_score,
            "score": self.score,
            "quality_score": self.quality_score,
            "content": self.content,
            "summary": self.summary,
            "feed_weight": self.feed_weight,
            "feed_url": self.feed_url,
            "content_hash": self.content_hash,
            "minhash_signature": self.minhash_signature,
            "tags": self.tags,
            "translation": self.translation,
        }


def list_articles(
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    sort_by: str | None = None,
    min_quality: float | None = None,
) -> list[ArticleListItem]:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles to return (default 20).
        feed_id: Optional feed ID to filter articles by a specific feed.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
        sort_by: Sort field — "quality" sorts by quality_score DESC, NULLS LAST.
        min_quality: Minimum quality_score filter (0.0-1.0).

    Returns:
        List of ArticleListItem objects.
    """
    return storage_list_articles(
        limit=limit,
        feed_id=feed_id,
        since=since,
        until=until,
        on=on,
        groups=groups,
        sort_by=sort_by,
        min_quality=min_quality,
    )


def get_article(article_id: str) -> ArticleListItem | None:
    """Get a single article by ID.

    Args:
        article_id: The ID of the article to retrieve.

    Returns:
        ArticleListItem object if found, None otherwise.
    """
    return storage_get_article(article_id)


def get_article_detail(article_id: str) -> dict | None:
    """Get full article details including content.

    Args:
        article_id: The ID of the article (can be truncated 8-char or full 32-char).

    Returns:
        Dict with all article fields.
        Returns None if article not found.
    """
    return storage_get_article_detail(article_id)


def search_articles_fts(
    query: str,
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    cross_encoder: bool = False,
) -> list[ArticleListItem]:
    """Search articles using FTS5 full-text search with BM25 scoring.

    Args:
        query: FTS5 query string (space-separated = AND, use quotes for phrases)
        limit: Maximum number of results (default 20)
        feed_id: Optional feed ID to filter by specific feed
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
        cross_encoder: If True, apply Cross-Encoder reranking after initial search.

    Returns:
        List of ArticleListItem sorted by score descending.
    """
    articles = storage_search_articles_fts(
        query=query,
        limit=limit,
        feed_id=feed_id,
        since=since,
        until=until,
        on=on,
        groups=groups,
    )
    if cross_encoder:
        from src.application.cross_encoder import cross_encoder as _cross_encoder_func

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                articles = executor.submit(
                    _cross_encoder_func, query, articles, limit
                ).result()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                f"Cross-Encoder model unavailable, skipping rerank: {e}"
            )
    # FTS5: gamma=0.0 (no vec_sim), delta=0.2 (BM25)
    return combine_scores(articles, alpha=0.3, beta=0.3, gamma=0.0, delta=0.2)


def search_articles_semantic(
    query_text: str,
    limit: int = 20,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    cross_encoder: bool = False,
) -> list[ArticleListItem]:
    """Search articles by semantic similarity with vector scoring.

    Args:
        query_text: Natural language query to search for
        limit: Maximum number of results to return
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
        cross_encoder: If True, apply Cross-Encoder reranking after initial search.

    Returns:
        List of ArticleListItem sorted by score descending.

    Raises:
        RuntimeError: If ML dependencies (chromadb, sentence-transformers) are not installed.
    """
    _check_ml_dependencies()
    articles = storage_search_articles_semantic(
        query_text=query_text,
        limit=limit,
        since=since,
        until=until,
        on=on,
        groups=groups,
    )
    if cross_encoder:
        from src.application.cross_encoder import cross_encoder as _cross_encoder_func

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                articles = executor.submit(
                    _cross_encoder_func, query_text, articles, limit
                ).result()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                f"Cross-Encoder model unavailable, skipping rerank: {e}"
            )
    # Semantic: gamma=0.2 (vec_sim), delta=0.0 (no BM25)
    return combine_scores(articles, alpha=0.3, beta=0.3, gamma=0.2, delta=0.0)
