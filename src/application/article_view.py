"""Article view operations - fetch URL or fill article content via Trafilatura."""

from datetime import datetime, timezone

import trafilatura
from scrapling import Selector

from src.storage import update_article_content
from src.utils.scraping_utils import fetch_with_fallback


def _extract_content(html: str, url: str) -> dict:
    """Extract content from HTML using Trafilatura.

    Args:
        html: Raw HTML content.
        url: Source URL (for Trafilatura reference).

    Returns:
        Dict with title, content (markdown), or error key.
    """
    result = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_images=False,
        include_tables=True,
        date_extraction_params={},
        only_with_metadata=True,
    )
    if not result:
        return {"error": "Trafilatura extraction failed - no content extracted"}
    return {"content": result}


def fetch_url_content(url: str, timeout: int = 30) -> dict:
    """Fetch URL and extract content as Markdown.

    Args:
        url: URL to fetch and extract.
        timeout: Request timeout in seconds (default 30).

    Returns:
        Dict with url, title, content, extracted_at on success.
        Dict with error key on failure.

    Trafilatura options:
        output_format="markdown", include_images=False, include_tables=True
    """
    response = fetch_with_fallback(url, timeout=timeout)
    if response is None:
        return {"error": f"Failed to fetch URL: {url}"}

    html = response.html_content
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")

    if not html or len(html) < 100:
        return {"error": f"Page appears empty or blocked: {url}"}

    # Extract title from HTML for response
    title = None
    try:
        root = Selector(html)
        title_els = root.css("title")
        if title_els and title_els[0].text:
            title = title_els[0].text.strip()
    except Exception:
        pass

    extracted = _extract_content(html, url)
    if "error" in extracted:
        return extracted

    return {
        "url": url,
        "title": title,
        "content": extracted["content"],
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_and_fill_article(article_id: str) -> dict:
    """Fetch article link from DB, extract content, update DB, return content.

    Args:
        article_id: Article ID in database (supports 8-char truncated).

    Returns:
        Dict with url, title, content, extracted_at on success.
        Dict with error key on failure.
    """
    from src.storage import get_article_detail

    article = get_article_detail(article_id)
    if not article:
        return {"error": f"Article not found: {article_id}"}

    link = article.get("link")
    if not link:
        return {"error": f"Article has no link: {article_id}"}

    # Fetch and extract
    extracted = fetch_url_content(link)
    if "error" in extracted:
        return extracted

    # Update database
    update_result = update_article_content(article_id, extracted["content"])
    if not update_result["success"]:
        return {"error": update_result["error"]}

    return {
        "url": link,
        "title": article.get("title"),
        "content": extracted["content"],
        "extracted_at": extracted["extracted_at"],
    }
