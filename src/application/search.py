"""Search result formatting functions for CLI presentation.

Separates formatting logic from CLI presentation, making search results
reusable by other callers without CLI dependencies.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from src.storage.sqlite import get_article, get_feed


def format_articles(items: list[dict[str, Any]], verbose: bool = False) -> list[dict[str, Any]]:
    """Format articles for display using unified score field interface.

    Assumes items are dicts from rank_*_results with a score field (0-1 normalized).
    No mode branching - all article types use the same formatting logic.

    Args:
        items: List of article dicts with score field from rank_*_results
        verbose: Include full details if True

    Returns:
        List of dicts with unified fields: id, title, source, date, score
    """
    return _format_items(items, verbose)


def _format_items(items: list[dict[str, Any]], verbose: bool) -> list[dict[str, Any]]:
    """Format articles for display using unified score field interface.

    Assumes items are dicts with score field from rank_*_results.
    Handles all article types (list, FTS, semantic) through unified interface.

    Args:
        items: List of article dicts with score field from rank_*_results
        verbose: Include full details if True

    Returns:
        List of dicts with unified fields: id, title, source, date, score
    """
    formatted = []
    for item in items:
        title = _truncate(item.get("title") or "No title", 60)
        date = _format_date_for_display(item.get("pub_date"))
        score_val = item.get("score")

        # Format score as percentage (0-1 normalized from rank_*_results)
        if score_val is not None:
            score = f"{int(score_val * 100)}%"
        else:
            score = "N/A"

        # Extract source - prefer feed_name (list/FTS) or domain from url (semantic)
        feed_name = item.get("feed_name")
        url = item.get("url")
        if feed_name:
            source = _truncate(feed_name, 15)
        elif url:
            try:
                parsed = urlparse(url)
                source = parsed.netloc[:15] if parsed.netloc else "-"
            except Exception:
                source = "-"
        else:
            source = "-"

        # Extract article ID - prefer id, fall back to sqlite_id
        article_id = item.get("id") or item.get("sqlite_id") or ""

        # Base fields always present
        base = {
            "id": article_id[:8] if article_id and not verbose else article_id,
            "title": title,
            "source": source,
            "date": date,
            "score": score,
        }

        # Add verbose-only fields based on what's available
        if verbose:
            # Link from FTS results
            if item.get("link"):
                base["link"] = item["link"]
            # Description from FTS results
            if item.get("description"):
                base["description_preview"] = _truncate(item["description"], 100)
            # URL and document from semantic results
            if item.get("url"):
                base["url"] = url
            if item.get("document"):
                base["document_preview"] = _truncate(item["document"], 150)

        formatted.append(base)
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
    return format_articles(results, verbose=verbose)


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
        ranked_result["feed_id"] = article.feed_id if article else None
        ranked_result["feed_name"] = article.feed_name if article else None
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
        # Add score field for unified interface (0-1 normalized value)
        r["score"] = r["final_score"]

    # Sort by final_score descending, return top_k
    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    return ranked[:top_k]


def rank_fts_results(articles: list[Any]) -> list[dict[str, Any]]:
    """Rank FTS search results with fixed score.

    FTS keyword search has no similarity metric, so all results get score=1.0.

    Args:
        articles: List of ArticleListItem from search_articles.

    Returns:
        List of dicts with all original article fields PLUS score=1.0.
        Returns empty list if input is empty.
    """
    if not articles:
        return []
    return [{**vars(article), "score": 1.0} for article in articles]


def rank_list_results(items: list[Any]) -> list[dict[str, Any]]:
    """Rank list results with fixed score.

    List results have no similarity metric, so all results get score=1.0.

    Args:
        items: List of ArticleListItem from list_articles.

    Returns:
        List of dicts with all original item fields PLUS score=1.0.
        Returns empty list if input is empty.
    """
    if not items:
        return []
    return [{**vars(item), "score": 1.0} for item in items]


def format_fts_results(articles: list[Any], verbose: bool = False) -> list[dict[str, Any]]:
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
    return format_articles(articles, verbose=verbose)


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


def print_articles(items: list[Any], verbose: bool = False) -> None:
    """Print formatted articles to console.

    Args:
        items: List of ArticleListItem (list/search) or dict (semantic).
        verbose: If True, show detailed output with full fields
    """
    import click

    if not items:
        click.secho("No articles found.")
        return

    # Unified header
    click.secho("ID | Title | Source | Date | Score\n" + "-" * 80)

    for item in items:
        # Determine if this is an ArticleListItem or dict
        if hasattr(item, '__dataclass_fields__'):  # ArticleListItem
            article_id = item.id
            title = item.title
            source = item.feed_name
            date = item.pub_date
            score = item.score
            link = item.link
            description = item.description
        else:  # dict (semantic search)
            article_id = item.get("sqlite_id") or item.get("id") or ""
            title = item.get("title") or "No title"
            url = item.get("url")
            source = urlparse(url).netloc[:15] if url else "-"
            date = item.get("pub_date") or "-"
            score = item.get("score", 1.0)
            link = url
            description = item.get("document")

        if verbose:
            _print_article_verbose({
                "id": article_id,
                "title": title,
                "source": source,
                "date": date,
                "score": score,
                "link": link,
                "description_preview": description[:100] + "..." if description and len(description) > 100 else description,
            })
        else:
            click.secho(f"{article_id[:8]} | {title[:60]} | {source[:15]} | {date[:10] if date else '-'} | {str(score)[:4]}")


def _print_article_verbose(item: dict[str, Any]) -> None:
    """Print a single article in verbose mode."""
    import click
    click.secho(f"\nTitle: {item['title']}")
    if item.get('id'): click.secho(f"ID: {item['id']}")
    if item.get('source'): click.secho(f"Source: {item['source']}")
    if item.get('date'): click.secho(f"Date: {item['date']}")
    if item.get('link'): click.secho(f"Link: {item['link']}")
    if item.get('url'): click.secho(f"URL: {item['url']}")
    if item.get('description_preview'): click.secho(f"Description: {item['description_preview']}")
    if item.get('document_preview'): click.secho(f"Content preview: {item['document_preview']}")
