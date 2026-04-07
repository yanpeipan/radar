"""LLM summarization application logic.

Provides process_article_llm() that runs summarize + quality scoring +
keyword extraction on a single article and persists results to SQLite + ChromaDB.
"""

from __future__ import annotations

import logging
from typing import Any

from src.application.llm import (
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

    if not content:
        return {
            "success": False,
            "error": "No content available for summarization",
            "article_id": article_id,
            "title": title,
        }

    # Run LLM tasks in parallel for efficiency

    summary_task = summarize_text(content, title)
    quality_task = score_quality(content, title)
    keywords_task = extract_keywords(content)

    summary, was_truncated = await summary_task
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
