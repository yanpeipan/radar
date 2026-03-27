"""Search result formatting functions for CLI presentation.

Separates formatting logic from CLI presentation, making search results
reusable by other callers without CLI dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from src.application.articles import ArticleListItem
from src.storage.sqlite import get_article, get_feed


def format_articles(items: list, mode: str = "list", verbose: bool = False) -> list[dict[str, Any]]:
    """Unified article list formatter for all display modes.

    Args:
        items: List of articles (type depends on mode)
        mode: 'list' for list_articles, 'fts' for search_articles, 'semantic' for rank_semantic_results
        verbose: Include full details if True

    Returns:
        List of dicts with unified fields: id, title, source, date, score
    """
    if mode == "list":
        return _format_list_items(items, verbose)
    elif mode == "fts":
        return _format_fts_items(items, verbose)
    elif mode == "semantic":
        return _format_semantic_items(items, verbose)
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _format_list_items(items: list[ArticleListItem], verbose: bool) -> list[dict[str, Any]]:
    """Format list_articles output (ArticleListItem list)."""
    formatted = []
    for article in items:
        title = _truncate(article.title, 60) if article.title else "No title"
        source = _truncate(article.feed_name, 15) if article.feed_name else "Unknown"
        date = _format_date_for_display(article.pub_date)
        article_id = article.id
        if verbose:
            formatted.append({
                "id": article_id,
                "title": title,
                "source": source,
                "date": date,
                "score": "LIST",
            })
        else:
            formatted.append({
                "id": article_id[:8],
                "title": title,
                "source": source,
                "date": date,
                "score": "LIST",
            })
    return formatted


def _format_fts_items(items: list[ArticleListItem], verbose: bool) -> list[dict[str, Any]]:
    """Format search_articles output (ArticleListItem list)."""
    formatted = []
    for article in items:
        title = _truncate(article.title, 60) if article.title else "No title"
        source = _truncate(article.feed_name, 15) if article.feed_name else "Unknown"
        date = _format_date_for_display(article.pub_date)
        article_id = article.id
        if verbose:
            desc_preview = _truncate(article.description, 100) if article.description else ""
            formatted.append({
                "id": article_id,
                "title": title,
                "source": source,
                "date": date,
                "score": "FTS",
                "link": article.link or "",
                "description_preview": desc_preview,
            })
        else:
            formatted.append({
                "id": article_id[:8],
                "title": title,
                "source": source,
                "date": date,
                "score": "FTS",
            })
    return formatted


def _format_semantic_items(items: list[dict[str, Any]], verbose: bool) -> list[dict[str, Any]]:
    """Format rank_semantic_results output (dict list)."""
    formatted = []
    for result in items:
        title = result.get("title") or "No title"
        url = result.get("url") or ""
        sqlite_id = result.get("sqlite_id")
        norm_sim = result.get("norm_similarity")
        distance = result.get("distance")

        # Use norm_similarity if available (from rank_semantic_results),
        # otherwise compute from distance for fallback
        if norm_sim is not None:
            score = f"{int(norm_sim * 100)}%"
        elif distance is not None:
            cos_sim = max(0.0, 1.0 - (distance * distance / 2.0))
            score = f"{int(cos_sim * 100)}%"
        else:
            score = "N/A"

        # Extract domain from URL for source field
        if url:
            try:
                parsed = urlparse(url)
                source = parsed.netloc[:15] if parsed.netloc else "-"
            except Exception:
                source = "-"
        else:
            source = "-"

        if verbose:
            formatted.append({
                "id": sqlite_id[:8] if sqlite_id else "",
                "title": title,
                "source": source,
                "date": "-",
                "score": score,
                "url": url,
                "document_preview": _truncate(result.get("document"), 150) if result.get("document") else "",
            })
        else:
            formatted.append({
                "id": sqlite_id[:8] if sqlite_id else "",
                "title": title,
                "source": source,
                "date": "-",
                "score": score,
            })
    return formatted


def format_semantic_results(results: list[dict[str, Any]], verbose: bool = False) -> list[dict[str, Any]]:
    """Format semantic search results for display.

    Takes output from rank_semantic_results (list of dicts with article_id,
    sqlite_id, title, url, distance, document, norm_similarity) and formats
    for unified CLI presentation.

    Args:
        results: List of dicts from rank_semantic_results with keys:
            - article_id: ChromaDB ID (guid)
            - sqlite_id: SQLite nanoid or None
            - title: Article title or None
            - url: Article URL or None
            - distance: L2 distance (float) or None
            - document: Full content text or None
            - norm_similarity: Normalized similarity score (0-1) from ranking
        verbose: If True, include full details (id, url, document preview).
                 If False, show truncated summary.

    Returns:
        List of dicts with unified formatted fields:
        - id: sqlite_id[:8] or "" (non-verbose), full sqlite_id or "" (verbose)
        - title: article title (truncated to 60 chars)
        - source: domain from url (truncated to 15 chars) or "-"
        - date: "-" (semantic search has no date)
        - score: norm_similarity * 100 as percentage like "85%" or "N/A"
        - url: full url (verbose only)
        - document_preview: truncated content (verbose only)
    """
    return format_articles(results, mode="semantic", verbose=verbose)


def rank_semantic_results(results: list[dict[str, Any]], top_k: int = 10) -> list[dict[str, Any]]:
    """Rank semantic search results using multi-factor scoring.

    Applies ranking algorithm combining normalized cosine similarity (50%),
    normalized freshness (30%), and source weight (20%).

    Args:
        results: List of dicts from search_articles_semantic with keys:
            - article_id: ChromaDB ID (guid)
            - sqlite_id: SQLite nanoid or None
            - title: Article title or None
            - url: Article URL or None
            - distance: L2 distance (float) or None
            - document: Full content text or None
        top_k: Maximum number of results to return after ranking.

    Returns:
        List of dicts with all original keys PLUS:
        - cos_sim: Cosine similarity computed from distance
        - norm_similarity: Min-max normalized similarity (0-1)
        - norm_freshness: Normalized freshness score (0-1)
        - final_score: Weighted combination score (0-1)
        Results sorted by final_score descending, limited to top_k.
        Results with sqlite_id=None (pre-v1.8) are excluded.
    """
    # Filter pre-v1.8 articles (those without SQLite ID / no embedding)
    ranked = []
    for result in results:
        sqlite_id = result.get("sqlite_id")
        if sqlite_id is None:
            continue  # Skip articles without embeddings (pre-v1.8)

        # Look up pub_date from SQLite
        article = get_article(sqlite_id)
        pub_date = article.pub_date if article else None

        # Calculate cosine similarity from L2 distance
        distance = result.get("distance")
        if distance is not None:
            cos_sim = max(0.0, 1.0 - (distance * distance / 2.0))
        else:
            cos_sim = 0.0

        # Calculate freshness score: max(0.0, 1 - days_ago / 30)
        if pub_date:
            try:
                pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - pub_dt).days
                freshness = max(0.0, 1.0 - days_ago / 30)
            except (ValueError, TypeError):
                freshness = 0.0
        else:
            freshness = 0.0

        # Get source weight from feed's weight field
        feed_id = article.feed_id if article else None
        if feed_id:
            feed = get_feed(feed_id)
            source_weight = feed.weight if feed and feed.weight is not None else 0.3
        else:
            source_weight = 0.3

        # Build ranked result with all original keys plus computed scores
        ranked_result = {**result}
        ranked_result["cos_sim"] = cos_sim
        ranked_result["freshness"] = freshness
        ranked_result["source_weight"] = source_weight
        ranked.append(ranked_result)

    if not ranked:
        return []

    # Min-max normalize similarity across all ranked results
    cos_sims = [r["cos_sim"] for r in ranked]
    min_cos = min(cos_sims)
    max_cos = max(cos_sims)
    for r in ranked:
        if max_cos > min_cos:
            r["norm_similarity"] = (r["cos_sim"] - min_cos) / (max_cos - min_cos)
        else:
            r["norm_similarity"] = 1.0
        r["norm_freshness"] = r["freshness"]

        # Calculate final score: 0.5 * norm_similarity + 0.3 * norm_freshness + 0.2 * source_weight
        r["final_score"] = (
            0.5 * r["norm_similarity"]
            + 0.3 * r["norm_freshness"]
            + 0.2 * r["source_weight"]
        )

    # Sort by final_score descending, return top_k
    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    return ranked[:top_k]


def format_fts_results(articles: list[ArticleListItem], verbose: bool = False) -> list[dict[str, Any]]:
    """Format FTS5 keyword search results for display.

    Takes output from search_articles (list of ArticleListItem) and
    formats fields for unified CLI presentation.

    Args:
        articles: List of ArticleListItem from search_articles with keys:
            - title: Article title or None
            - feed_name: Name of the feed
            - pub_date: Publication date or None
            - link: URL link or None
            - description: Short description or None
        verbose: If True, include link and description preview.
                 If False, show truncated summary.

    Returns:
        List of dicts with unified formatted fields:
        - id: article_id[:8] (non-verbose) or article_id (verbose)
        - title: article title (truncated to 60 chars)
        - source: feed_name (truncated to 15 chars)
        - date: pub_date (formatted as yyyy-mm-dd)
        - score: "FTS" (indicates FTS keyword search)
        - link: article link (verbose only)
        - description_preview: truncated description (verbose only)
    """
    return format_articles(articles, mode="fts", verbose=verbose)


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _format_date_for_display(pub_date: str | None) -> str:
    """Convert pub_date to yyyy-mm-dd format for display.

    Handles RFC 2822 dates from RSS feeds (e.g., 'Thu, 26 Mar 2026 10:30:00 +0000')
    and ISO format dates (e.g., '2026-03-26').

    Args:
        pub_date: Publication date string or None.

    Returns:
        Formatted date string (yyyy-mm-dd) or "-" if invalid/None.
    """
    if not pub_date:
        return "-"

    # Try parsing as RFC 2822 (RSS feed format)
    try:
        dt = parsedate_to_datetime(pub_date)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Try parsing as ISO format (already normalized)
    try:
        dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Fallback: return as-is (should not reach here normally)
    return pub_date[:10] if len(pub_date) >= 10 else pub_date
