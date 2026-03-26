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
from src.storage import list_feeds as storage_list_feeds, store_article_async, add_article_embedding
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

            # Generate embedding for semantic search (D-09)
            try:
                await asyncio.to_thread(
                    add_article_embedding,
                    article_id=article_guid,
                    title=article.get("title") or "",
                    content=article.get("content") or article.get("description") or "",
                    url=article.get("link") or "",
                )
            except Exception as e:
                logger.warning("Failed to add embedding for article %s: %s", article_guid, e)
                # Don't re-raise - embedding failure should not fail the fetch

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


async def fetch_all_async(concurrency: int = 10):
    """Fetch new articles from all subscribed feeds concurrently.

    Uses asyncio.Semaphore to limit concurrent HTTP requests to `concurrency`
    (default 10). SQLite writes are serialized via asyncio.Lock + asyncio.to_thread()
    to prevent 'database is locked' errors.

    This is an async generator that yields results as each feed completes,
    enabling real-time progress tracking via asyncio.as_completed().

    Args:
        concurrency: Maximum number of concurrent feed crawls. Default is 10.

    Yields:
        Dict with feed_id, feed_name, new_articles, error (if any).
    """
    feeds = storage_list_feeds()
    if not feeds:
        return

    semaphore = asyncio.Semaphore(concurrency)

    async def process_feed_with_semaphore(feed: Feed, index: int) -> tuple:
        """Process a single feed within the semaphore limit."""
        async with semaphore:
            result = await fetch_one_async(feed)
            return index, feed, result

    # Create tasks for all feeds - semaphore limits actual concurrency
    tasks = [process_feed_with_semaphore(feed, i) for i, feed in enumerate(feeds)]

    # Use as_completed to yield results as they complete
    for coro in asyncio.as_completed(tasks):
        index, feed, result = await coro
        yield {
            "feed_id": feed.id,
            "feed_name": feed.name,
            "new_articles": result.get("new_articles", 0),
            "error": result.get("error") if result.get("new_articles", 0) == 0 else None,
        }
