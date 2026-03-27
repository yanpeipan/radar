"""Related articles business logic using ChromaDB semantic similarity."""

from __future__ import annotations

from src.storage.vector import get_related_articles as storage_get_related_articles


def get_related_articles_display(article_id: str, limit: int = 5, verbose: bool = False) -> list[dict[str, str]]:
    """Get formatted related articles for display.

    Args:
        article_id: The article ID to find related articles for.
        limit: Maximum number of related articles to return (default 5).
        verbose: If True, include document preview in results.

    Returns:
        List of dicts with keys: title, url, similarity, document_preview (if verbose).
        If article exists but has no embedding, returns list with a single dict
        containing {"no_embedding": True}.
    """
    results = storage_get_related_articles(article_id=article_id, limit=limit)

    if not results:
        # Check if article exists but has no embedding
        from src.storage.sqlite import get_article
        article = get_article(article_id)
        if article:
            return [{"no_embedding": True}]
        return []

    formatted = []
    for result in results:
        title = result.get("title") or "No title"
        url = result.get("url") or ""
        distance = result.get("distance")
        similarity = f"{max(0, round((1 - distance) * 100, 1))}%" if distance is not None else "N/A"

        item: dict[str, str] = {
            "title": title,
            "url": url,
            "similarity": similarity,
        }

        if verbose:
            doc = result.get("document") or ""
            if doc:
                preview = doc[:150] + "..." if len(doc) > 150 else doc
                item["document_preview"] = preview

        formatted.append(item)

    return formatted
