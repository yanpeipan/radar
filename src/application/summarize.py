"""LLM summarization application logic.

Provides process_article_llm() that runs summarize + quality scoring +
keyword extraction on a single article and persists results to SQLite + ChromaDB.
"""

from __future__ import annotations

import logging
from typing import Any

from src.llm.core import (
    extract_keywords,
    score_quality,
    summarize_text,
)
from src.storage import (
    get_article_with_llm,
    update_article_llm,
)
from src.storage.vector import (
    upsert_article_keywords,
    upsert_article_summary,
)

logger = logging.getLogger(__name__)


async def process_article_llm(
    article_id: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Process a single article with LLM: summarize, score quality, extract keywords.

    Args:
        article_id: Full or 8-char truncated article ID.
        force: Re-process even if article already has summary.

    Returns:
        dict with keys: success, error, article_id, title, summary,
        quality_score, keywords, was_truncated, provider, model

    The was_truncated field indicates whether the input content was
    truncated due to token limits during summarization.
    """
    try:
        article = get_article_with_llm(article_id)
    except ValueError as e:
        return {"success": False, "error": str(e), "article_id": article_id}

    if article is None:
        return {
            "success": False,
            "error": f"Article not found: {article_id}",
            "article_id": article_id,
        }

    # Skip if already summarized (unless force=True)
    if article.get("summary") and not force:
        return {
            "success": False,
            "error": "Article already has a summary. Use --force to re-summarize.",
            "article_id": article_id,
            "title": article.get("title", ""),
        }

    title = article.get("title", "")
    content = article.get("content") or article.get("description") or ""

    # If no content, try to fetch from the article's URL
    if not content:
        from src.application.article_view import fetch_and_fill_article

        logger.info("No content for article %s, fetching from URL...", article_id)
        fetch_result = fetch_and_fill_article(article_id)
        if "error" in fetch_result:
            return {
                "success": False,
                "error": f"No content available and failed to fetch URL: {fetch_result['error']}",
                "article_id": article_id,
                "title": title,
            }
        content = fetch_result.get("content", "")
        logger.info(
            "Successfully fetched %d chars for article %s", len(content), article_id
        )

    # Run LLM tasks in parallel for efficiency

    summary_task = summarize_text(content, title)
    quality_task = score_quality(content, title)
    keywords_task = extract_keywords(content)

    print(f"[DEBUG] content length: {len(content)}, title: {title[:30]}")
    summary, was_truncated = await summary_task
    print(f"[DEBUG] summary result: {repr(summary[:50]) if summary else 'EMPTY'}")
    quality_score = await quality_task
    keywords = await keywords_task

    # Persist to SQLite
    update_result = update_article_llm(
        article_id,
        summary=summary,
        quality_score=quality_score,
        keywords=keywords,
        tags=[],  # Tags are auto-generated from keywords if needed
    )

    if not update_result.get("success"):
        logger.warning(
            "Failed to update SQLite for article %s: %s",
            article_id,
            update_result.get("error"),
        )

    # Persist to ChromaDB
    url = article.get("link", "")
    published_at = article.get("published_at")

    try:
        upsert_article_summary(
            article_id=article_id,
            summary=summary,
            title=title,
            url=url,
            published_at=published_at,
        )
    except Exception as e:
        logger.warning("Failed to upsert summary to ChromaDB: %s", e)

    try:
        upsert_article_keywords(
            article_id=article_id,
            keywords=keywords,
            title=title,
            url=url,
            published_at=published_at,
        )
    except Exception as e:
        logger.warning("Failed to upsert keywords to ChromaDB: %s", e)

    return {
        "success": True,
        "error": None,
        "article_id": article_id,
        "title": title,
        "summary": summary,
        "quality_score": quality_score,
        "keywords": keywords,
        "was_truncated": was_truncated,
        "provider": None,  # Available via LLMClient but kept opaque for simplicity
        "model": None,
    }


async def process_article_llm_batch(
    article_ids: list[str],
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Process multiple articles with LLM, respecting concurrency limits.

    Args:
        article_ids: List of article IDs to process.
        force: Re-process even if already summarized.

    Returns:
        List of result dicts (one per article).
    """
    import asyncio

    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent

    async def process_one(aid: str) -> dict[str, Any]:
        async with semaphore:
            return await process_article_llm(aid, force=force)

    tasks = [process_one(aid) for aid in article_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            output.append(
                {
                    "success": False,
                    "error": str(result),
                    "article_id": article_ids[i],
                }
            )
        else:
            output.append(result)
    return output


async def summarize_article_content(
    url: str,
    title: str,
    content: str,
    target_lang: str,
) -> tuple[str, str | None, float, list[str]]:
    """Summarize article content for on-demand report generation.

    Runs LLM summarization, quality scoring, and keyword extraction on raw
    article content (without requiring a stored article_id). Optionally
    translates the summary to the target language.

    Args:
        url: Article URL (used for logging only).
        title: Article title.
        content: Article body text.
        target_lang: Target language code (e.g., "zh", "en").

    Returns:
        Tuple of (summary, content_or_None, quality_score, keywords).
        - summary: Translated LLM summary (or original if target_lang=="en")
        - content_or_None: Always None (reserved for future use)
        - quality_score: Quality score 0.0-1.0
        - keywords: List of extracted keywords
    """
    import asyncio

    if not content:
        return "", None, 0.0, []

    semaphore = asyncio.Semaphore(5)

    async def run_llm() -> tuple[str, float, list[str]]:
        async with semaphore:
            summary_task = summarize_text(content, title)
            quality_task = score_quality(content, title)
            keywords_task = extract_keywords(content)
            summary, _ = await summary_task
            quality = await quality_task
            keywords = await keywords_task
            return summary, quality, keywords

    summary, quality, keywords = await run_llm()

    # Translate if target language is not English
    if target_lang and target_lang.lower() != "en":
        try:
            from src.llm.chains import get_translate_chain

            translated = await get_translate_chain().ainvoke(
                {"text": summary, "target_lang": target_lang}
            )
            summary = translated
        except Exception as e:
            logger.warning("Translation failed for article %s: %s", url, e)

    return summary, None, quality, keywords
