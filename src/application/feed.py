"""Feed fetching use cases - fetch single feed or all feeds via providers."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from src.application.config import get_timezone, get_default_feed_weight
from src.models import Feed, FeedMetaData
from src.providers import discover
from src.storage import list_feeds as storage_list_feeds, get_feed as storage_get_feed, remove_feed as storage_remove_feed, update_feed as storage_update_feed, upsert_feed
from src.utils import generate_article_id, generate_feed_id

logger = logging.getLogger(__name__)


class FeedNotFoundError(Exception):
    """Raised when a feed is not found in the database."""


def add_feed(url: str, weight: float | None = None, feed_meta_data: "FeedMetaData | None" = None) -> tuple[Feed, bool]:
    """Add a new feed by URL.

    Uses provider.parse_feed to fetch metadata and provider.crawl to validate.

    Args:
        url: The URL of the feed to add.
        weight: Optional feed weight for semantic search ranking. Defaults to config value.
        feed_meta_data: Optional provider-specific metadata (e.g., path selectors for WebpageProvider).

    Returns:
        The created Feed object.

    Raises:
        ValueError: If the feed already exists, cannot be fetched, or has no entries.
    """
    # Discover matching providers and try each until one succeeds
    providers = discover(url)

    feed_meta = None
    entries = None
    last_error = None

    # If we have metadata with selectors, insert feed first so selectors are available during crawl
    if feed_meta_data and feed_meta_data.selectors:
        feed_id = generate_feed_id()
        now = datetime.now(get_timezone()).isoformat()
        feed = Feed(
            id=feed_id,
            name=url,  # temporary name, will be updated
            url=url,
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at=now,
            weight=weight if weight is not None else get_default_feed_weight(),
            metadata=feed_meta_data.to_json(),
        )
        upsert_feed(feed)
    else:
        feed_id = generate_feed_id()
        now = datetime.now(get_timezone()).isoformat()
        feed = Feed(
            id=feed_id,
            name=url,
            url=url,
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at=now,
            weight=weight if weight is not None else get_default_feed_weight(),
            metadata=None,
        )

    for provider in providers:
        try:
            feed_meta = provider.parse_feed(url)
            result = provider.fetch_articles(feed)
            articles = result.articles
            if articles:
                break  # Success
        except Exception as e:
            last_error = e
            continue  # Try next provider

    if feed_meta is None or articles is None:
        if last_error:
            raise ValueError(f"All providers failed: {last_error}")
        raise ValueError("No provider could fetch feed metadata")

    if not articles:
        raise ValueError("No entries found in feed")

    # Check if feed already exists using storage function
    # Create new feed (or update existing)
    now = datetime.now(get_timezone()).isoformat()

    # Use upsert to insert or update (reuses feed_id from pre-insert if present)
    feed = Feed(
        id=feed_id,
        name=feed_meta.name,
        url=url,
        etag=feed_meta.etag,
        last_modified=feed_meta.last_modified,
        last_fetched=now,
        created_at=now,
        weight=weight if weight is not None else get_default_feed_weight(),
        metadata=feed_meta_data.to_json() if feed_meta_data else None,
    )
    return upsert_feed(feed)


def register_feed(feed_url: str, feed_name: str | None = None, weight: float | None = None, feed_meta_data: "FeedMetaData | None" = None) -> tuple[Feed, bool]:
    """Register a pre-discovered feed without crawling.

    Use for feeds that were already validated (e.g., via discover_feeds).
    This skips provider discovery and crawling - just saves the feed record.
    Articles are fetched later via fetch_one/fetch_all.

    Args:
        feed_url: The URL of the feed to register.
        feed_name: Optional name. If not provided, URL is used as name.
        weight: Optional feed weight for semantic search ranking.
        feed_meta_data: Optional provider-specific metadata (e.g., selectors for WebpageProvider).

    Returns:
        Tuple of (saved Feed object, is_new).
    """
    import json as json_module
    from src.models import Feed
    from src.application.config import get_default_feed_weight

    # Preserve existing metadata selectors if new metadata doesn't have selectors
    # This prevents overwriting existing selectors when updating via CLI
    if feed_meta_data and feed_meta_data.selectors is None:
        from src.storage import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metadata FROM feeds WHERE url = ?", (feed_url,))
            row = cursor.fetchone()
            if row and row["metadata"]:
                try:
                    existing_meta = json_module.loads(row["metadata"])
                    if existing_meta.get("selectors"):
                        feed_meta_data = FeedMetaData(
                            feed_type=feed_meta_data.feed_type,
                            selectors=existing_meta["selectors"]
                        )
                except (json_module.JSONDecodeError, TypeError):
                    pass

    now = datetime.now(get_timezone()).isoformat()
    feed = Feed(
        id=generate_feed_id(),
        name=feed_name or feed_url,
        url=feed_url,
        etag=None,
        last_modified=None,
        last_fetched=None,
        created_at=now,
        weight=weight if weight is not None else get_default_feed_weight(),
        metadata=feed_meta_data.to_json() if feed_meta_data else None,
    )
    return upsert_feed(feed)


def list_feeds() -> list[Feed]:
    """List all feeds with article counts.

    Returns:
        List of Feed objects with article counts available via articles_count attribute.
    """
    return storage_list_feeds()


def get_feed(feed_id: str) -> Optional[Feed]:
    """Get a single feed by ID.

    Args:
        feed_id: The ID of the feed to retrieve.

    Returns:
        The Feed object, or None if not found.
    """
    return storage_get_feed(feed_id)


def remove_feed(feed_id: str) -> bool:
    """Remove a feed and all its articles.

    Args:
        feed_id: The ID of the feed to remove.

    Returns:
        True if the feed was deleted, False if not found.
    """
    return storage_remove_feed(feed_id)


def fetch_one(feed_or_id: str | Feed) -> dict:
    """Fetch new articles from a single feed using provider pattern.

    Args:
        feed_or_id: The Feed object or the ID of the feed to refresh.

    Returns:
        Dict with new_articles count and optional error.

    Raises:
        FeedNotFoundError: If the feed does not exist.
    """
    if isinstance(feed_or_id, Feed):
        feed = feed_or_id
    else:
        feed = get_feed(feed_or_id)
        if not feed:
            raise FeedNotFoundError(f"Feed not found: {feed_or_id}")

    # Use discover to find provider for this feed URL
    providers = discover(feed.url)
    if not providers:
        return {"new_articles": 0, "error": f"No provider for {feed.url}"}

    provider = providers[0]  # highest priority match
    provider_name = provider.__class__.__name__.replace("Provider", "")

    # Crawl using the discovered provider
    try:
        result = provider.fetch_articles(feed)
        articles = result.articles
    except Exception as e:
        logger.error("Failed to crawl %s: %s", feed.url, e)
        return {"new_articles": 0, "error": str(e)}

    if not articles:
        return {"new_articles": 0}

    # Build article records with feed_id
    parsed_articles = []
    for article in articles:
        article_guid = article.get("guid") or generate_article_id(article)
        parsed_articles.append({
            "guid": article_guid,
            "title": article.get("title") or "",
            "content": article.get("content") or article.get("description") or "",
            "link": article.get("link") or "",
            "feed_id": feed.id,
            "pub_date": article.get("pub_date"),
        })

    if not parsed_articles:
        return {"new_articles": 0}

    # Batch upsert all articles
    from src.storage.sqlite.impl import upsert_articles
    article_id_map = upsert_articles(parsed_articles)
    new_count = len(article_id_map)

    # Update feed metadata after successful fetch
    if new_count > 0:
        now = datetime.now(get_timezone()).isoformat()
        storage_update_feed(feed.id, now)

    return {"new_articles": new_count}


def fetch_all() -> dict:
    """Fetch new articles from all subscribed feeds.

    Returns:
        Dict with total_new, success_count, error_count, errors.
    """
    feeds = list_feeds()
    if not feeds:
        return {"total_new": 0, "success_count": 0, "error_count": 0, "errors": []}

    total_new = 0
    success_count = 0
    error_count = 0
    errors = []

    for feed_obj in feeds:
        try:
            result = fetch_one(feed_obj)
            if "error" in result and result.get("new_articles", 0) == 0:
                # Error but no articles - likely no provider
                pass
            if result.get("new_articles", 0) > 0:
                total_new += result["new_articles"]
            success_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f"{feed_obj.name}: {e}")

    return {
        "total_new": total_new,
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors,
    }
