"""Async concurrent fetch with asyncio.Semaphore and SQLite serialization.

Provides fetch_all_async() for concurrent feed fetching with:
- asyncio.Semaphore for concurrency limiting (default 10)
- asyncio.Lock + asyncio.to_thread() for SQLite write serialization
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.models import Feed
from src.providers import discover_or_default
from src.storage import list_feeds as storage_list_feeds, store_article_async
from src.utils import generate_article_id

logger = logging.getLogger(__name__)


async def fetch_one_async(feed: Feed) -> dict:
    """Fetch new articles from a single feed asynchronously.

    Args:
        feed: Feed object to refresh.

    Returns:
        Dict with new_articles count and optional error.
    """
    # Skip 'crawled' system feed - it has no URL to refresh
    if feed.id == "crawled":
        return {"new_articles": 0}

    # Use discover_or_default to find provider for this feed URL
    providers = discover_or_default(feed.url)
    if not providers:
        return {"new_articles": 0, "error": f"No provider for {feed.url}"}

    provider = providers[0]  # highest priority match

    # Crawl using the discovered provider's async method
    try:
        raw_items = await provider.crawl_async(feed.url)
    except Exception as e:
        logger.error("Failed to crawl_async %s: %s", feed.url, e)
        return {"new_articles": 0, "error": str(e)}

    if not raw_items:
        return {"new_articles": 0}

    # Parse and store each item (store_article_async serializes DB writes)
    new_count = 0
    articles_needing_tags = []

    for raw in raw_items:
        article = provider.parse(raw)
        article_guid = article.get("guid") or generate_article_id(article)

        # Use async store that serializes writes via asyncio.Lock + to_thread
        try:
            await store_article_async(
                guid=article_guid,
                title=article.get("title") or "",
                content=article.get("content") or article.get("description") or "",
                link=article.get("link") or "",
                feed_id=feed.id,
                pub_date=article.get("pub_date"),
            )
            new_count += 1
            articles_needing_tags.append(
                (article_guid, article.get("title"), article.get("description"))
            )
        except Exception as e:
            logger.warning("Failed to store article %s: %s", article_guid, e)
            continue

    # Apply tag rules AFTER store to avoid nested connection writes
    from src.tags.tag_rules import apply_rules_to_article
    for article_id, title, description in articles_needing_tags:
        try:
            matched_tags = apply_rules_to_article(article_id, title, description)
            if matched_tags:
                logger.info(f"Auto-tagged article {article_id} with: {matched_tags}")
        except Exception as e:
            logger.warning(f"Failed to apply tag rules to article {article_id}: {e}")

    return {"new_articles": new_count}


async def fetch_all_async(concurrency: int = 10) -> dict:
    """Fetch new articles from all subscribed feeds concurrently.

    Uses asyncio.Semaphore to limit concurrent HTTP requests to `concurrency`
    (default 10). SQLite writes are serialized via asyncio.Lock + asyncio.to_thread()
    to prevent 'database is locked' errors.

    Args:
        concurrency: Maximum number of concurrent feed crawls. Default is 10.

    Returns:
        Dict with total_new, success_count, error_count, errors.
    """
    feeds = storage_list_feeds()
    if not feeds:
        return {"total_new": 0, "success_count": 0, "error_count": 0, "errors": []}

    semaphore = asyncio.Semaphore(concurrency)

    async def process_feed_with_semaphore(feed: Feed) -> dict:
        """Process a single feed within the semaphore limit."""
        async with semaphore:
            return await fetch_one_async(feed)

    # Create tasks for all feeds - semaphore limits actual concurrency
    tasks = [process_feed_with_semaphore(feed) for feed in feeds]

    # gather with return_exceptions=True so one failure doesn't cancel others
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate results
    total_new = 0
    success_count = 0
    error_count = 0
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            error_count += 1
            errors.append(f"{feeds[i].name}: {result}")
        else:
            if result.get("new_articles", 0) > 0:
                total_new += result["new_articles"]
            if "error" in result and result.get("new_articles", 0) == 0:
                # Error but no articles
                error_count += 1
                errors.append(f"{feeds[i].name}: {result.get('error')}")
            else:
                success_count += 1

    return {
        "total_new": total_new,
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors,
    }
