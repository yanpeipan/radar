"""Search result formatting functions for CLI presentation.

Separates formatting logic from CLI presentation, making search results
reusable by other callers without CLI dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from src.application.articles import ArticleListItem
from src.storage.sqlite import get_article


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
    formatted = []
    for result in results:
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


# Source weight configuration for ranking
_SOURCE_WEIGHTS = {
    "openai.com": 1.0,
    "arxiv.org": 0.9,
    "medium.com": 0.5,
    "default": 0.3,
}


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

        # Get source weight via domain suffix match
        url = result.get("url") or ""
        domain = ""
        if url:
            parsed = urlparse(url)
            domain = parsed.netloc
        source_weight = _SOURCE_WEIGHTS.get("default")
        for known_domain, weight in _SOURCE_WEIGHTS.items():
            if known_domain != "default" and domain.endswith(known_domain):
                source_weight = weight
                break

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
    formats fields with appropriate truncation for display.

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
        List of dicts with formatted fields:
        - title: article title (truncated to 50 chars)
        - source: feed_name (truncated to 25 chars)
        - date: pub_date (truncated to 10 chars)
        - link: article link (verbose only)
        - description_preview: truncated description (verbose only)
    """
    formatted = []
    for article in articles:
        title = _truncate(article.title, 50) if article.title else "No title"
        source = _truncate(article.feed_name, 25) if article.feed_name else "Unknown"
        date = _truncate(article.pub_date, 10) if article.pub_date else "No date"

        if verbose:
            desc_preview = _truncate(article.description, 100) if article.description else ""
            formatted.append({
                "title": title,
                "source": source,
                "date": date,
                "link": article.link or "",
                "description_preview": desc_preview,
            })
        else:
            formatted.append({
                "title": title,
                "source": source,
                "date": date,
            })
    return formatted


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
