"""Async concurrent fetch with asyncio.Semaphore and SQLite serialization.

Provides fetch_all_async() for concurrent feed fetching with:
- asyncio.Semaphore for concurrency limiting (default 10)
- asyncio.Lock + asyncio.to_thread() for SQLite write serialization
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from src.application.feed import FeedNotFoundError, fetch_one, get_feed
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
                # Lazy import to avoid torch dependency when embeddings are not needed
                from src.storage.vector import add_article_embedding
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
        except Exception as e:
            logger.warning("Failed to store article %s: %s", article_guid, e)
            continue

    return {"new_articles": new_count}


async def fetch_url_async(url: str) -> dict:
    """Fetch articles from a raw URL using discovered provider.

    Uses provider's crawl_async to fetch and parse articles, then stores
    them with embeddings applied (same as feed fetch).

    Args:
        url: URL to crawl.

    Returns:
        Dict with new_articles count, url, and optional error.
    """
    # Ensure system feed exists for crawled articles
    from src.storage import ensure_crawled_feed
    ensure_crawled_feed()

    # Use discover_or_default to find provider for this URL
    providers = discover_or_default(url)
    if not providers:
        return {"new_articles": 0, "url": url, "error": f"No provider for {url}"}

    provider = providers[0]  # highest priority match

    # Crawl using the discovered provider's async method
    try:
        raw_items = await provider.crawl_async(url)
    except Exception as e:
        logger.error("Failed to crawl_async %s: %s", url, e)
        return {"new_articles": 0, "url": url, "error": str(e)}

    if not raw_items:
        return {"new_articles": 0, "url": url}

    # Parse and store each item (store_article_async serializes DB writes)
    new_count = 0

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
                feed_id="crawled",  # System feed for crawled pages
                pub_date=article.get("pub_date"),
            )
            new_count += 1

            # Generate embedding for semantic search
            try:
                # Lazy import to avoid torch dependency when embeddings are not needed
                from src.storage.vector import add_article_embedding
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
        except Exception as e:
            logger.warning("Failed to store article %s: %s", article_guid, e)
            continue

    return {"new_articles": new_count, "url": url}


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


async def fetch_one_async_by_id(feed_id: str) -> dict:
    """Fetch one feed by ID using async-native path.

    Uses provider.crawl_async() and store_article_async() for true async
    HTTP and SQLite operations, avoiding asyncio.to_thread overhead.

    Args:
        feed_id: Feed ID to fetch.

    Returns:
        Dict with new_articles count and optional error.
    """
    feed = get_feed(feed_id)
    if not feed:
        raise FeedNotFoundError(f"Feed not found: {feed_id}")
    return await fetch_one_async(feed)


async def fetch_ids_async(ids: list[str], concurrency: int = 10):
    """Fetch new articles from specified feed IDs concurrently.

    Uses asyncio.Semaphore to limit concurrent HTTP requests to `concurrency`
    (default 10). SQLite writes are serialized via asyncio.Lock + asyncio.to_thread()
    to prevent 'database is locked' errors.

    Args:
        ids: List of feed IDs to fetch.
        concurrency: Maximum number of concurrent fetches. Default is 10.

    Yields:
        Dict with feed_id, new_articles, error (if any).
        Skips "Feed not found" errors gracefully (does not yield them).
    """
    if not ids:
        return

    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one_with_semaphore(id: str):
        async with semaphore:
            try:
                result = await asyncio.to_thread(fetch_one, id)
                return {"feed_id": id, **result}
            except FeedNotFoundError:
                # Skip "Feed not found" - feed doesn't exist in DB
                return None
            except Exception as e:
                # Yield other errors but continue to next feed
                return {"feed_id": id, "new_articles": 0, "error": str(e)}

    tasks = [fetch_one_with_semaphore(id) for id in ids]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result is not None:
            yield result
