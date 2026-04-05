"""Article operations for RSS reader.

Provides functions for listing and retrieving articles from the database.
Scoring and ranking logic is encapsulated in this layer.
"""

from __future__ import annotations

import concurrent.futures
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


def list_articles(
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
) -> list[ArticleListItem]:
    """List articles ordered by publication date.

    Args:
        limit: Maximum number of articles to return (default 20).
        feed_id: Optional feed ID to filter articles by a specific feed.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).

    Returns:
        List of ArticleListItem objects.
    """
    return storage_list_articles(
        limit=limit, feed_id=feed_id, since=since, until=until, on=on, groups=groups
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
    score: bool = True,
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
        score: If True, compute and sort by score (default). Set False when
            cross_encoder will override the sort anyway.
        cross_encoder: If True, apply Cross-Encoder reranking after initial search.

    Returns:
        List of ArticleListItem sorted by score descending (if score=True).
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
        with concurrent.futures.ThreadPoolExecutor() as executor:
            articles = executor.submit(cross_encoder, query, articles, limit).result()
        # After cross_encoder sets ce_score, recompute score with FTS5 weights
        articles = combine_scores(articles, alpha=0.3, beta=0.3, gamma=0.0, delta=0.2)
    elif score:
        # FTS5: gamma=0.0 (no vec_sim), delta=0.2 (BM25)
        articles = combine_scores(articles, alpha=0.3, beta=0.3, gamma=0.0, delta=0.2)
    return articles


def search_articles_semantic(
    query_text: str,
    limit: int = 20,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    score: bool = True,
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
        score: If True, compute and sort by score (default). Set False when
            cross_encoder will override the sort anyway.
        cross_encoder: If True, apply Cross-Encoder reranking after initial search.

    Returns:
        List of ArticleListItem sorted by score descending (if score=True).
    """
    articles = storage_search_articles_semantic(
        query_text=query_text,
        limit=limit,
        since=since,
        until=until,
        on=on,
        groups=groups,
    )
    if cross_encoder:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            articles = executor.submit(
                cross_encoder, query_text, articles, limit
            ).result()
        # After cross_encoder sets ce_score, recompute score with semantic weights
        articles = combine_scores(articles, alpha=0.3, beta=0.3, gamma=0.2, delta=0.0)
    elif score:
        # Semantic: gamma=0.2 (vec_sim), delta=0.0 (no BM25)
        articles = combine_scores(articles, alpha=0.3, beta=0.3, gamma=0.2, delta=0.0)
    return articles
