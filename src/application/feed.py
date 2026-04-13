"""Feed fetching use cases - fetch single feed or all feeds via providers."""

from __future__ import annotations

import logging
import time

from src.application.config import get_default_feed_weight, get_default_refresh_interval
from src.models import Feed, FeedMetaData
from src.providers import discover
from src.storage import get_feed as storage_get_feed
from src.storage import list_feeds as storage_list_feeds
from src.storage import remove_feed as storage_remove_feed
from src.storage import update_feed as storage_update_feed
from src.storage import update_feed_metadata as storage_update_feed_metadata
from src.storage import upsert_feed
from src.storage.sqlite.articles import _get_article_field
from src.utils import generate_article_id, generate_feed_id

logger = logging.getLogger(__name__)


class FeedNotFoundError(Exception):
    """Raised when a feed is not found in the database."""


def add_feed(
    url: str,
    weight: float | None = None,
    feed_meta_data: FeedMetaData | None = None,
    group: str | None = None,
    refresh_interval: int | None = None,
) -> tuple[Feed, bool]:
    """Add a new feed by URL.

    Uses provider.parse_feed to fetch metadata and provider.crawl to validate.

    Args:
        url: The URL of the feed to add.
        weight: Optional feed weight for semantic search ranking. Defaults to config value.
        feed_meta_data: Optional provider-specific metadata (e.g., path selectors for WebpageProvider).
        refresh_interval: Optional refresh interval in seconds. Defaults to config value.

    Returns:
        The created Feed object.

    Raises:
        ValueError: If the feed already exists, cannot be fetched, or has no entries.
    """
    # Discover matching providers and try each until one succeeds
    providers = discover(url)

    feed_meta = None
    last_error = None

    # If we have metadata with selectors, insert feed first so selectors are available during crawl
    if feed_meta_data and feed_meta_data.selectors:
        feed_id = generate_feed_id()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        feed = Feed(
            id=feed_id,
            name=url,  # temporary name, will be updated
            url=url,
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at=now,
            weight=weight if weight is not None else get_default_feed_weight(),
            metadata=feed_meta_data.to_json(),
            group=group,
            refresh_interval=refresh_interval
            if refresh_interval is not None
            else get_default_refresh_interval(),
        )
        upsert_feed(feed)
    else:
        feed_id = generate_feed_id()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        feed = Feed(
            id=feed_id,
            name=url,
            url=url,
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at=now,
            weight=weight if weight is not None else get_default_feed_weight(),
            metadata=None,
            group=group,
            refresh_interval=refresh_interval
            if refresh_interval is not None
            else get_default_refresh_interval(),
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
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    # Use upsert to insert or update (reuses feed_id from pre-insert if present)
    feed = Feed(
        id=feed_id,
        name=feed_meta.name,
        url=url,
        etag=result.etag,
        modified_at=result.modified_at,
        fetched_at=now,
        created_at=now,
        weight=weight if weight is not None else get_default_feed_weight(),
        metadata=feed_meta_data.to_json() if feed_meta_data else None,
        group=group,
        refresh_interval=refresh_interval
        if refresh_interval is not None
        else get_default_refresh_interval(),
    )
    return upsert_feed(feed)


def register_feed(
    feed_url: str,
    feed_name: str | None = None,
    weight: float | None = None,
    feed_meta_data: FeedMetaData | None = None,
    group: str | None = None,
    refresh_interval: int | None = None,
) -> tuple[Feed, bool]:
    """Register a pre-discovered feed without crawling.

    Use for feeds that were already validated (e.g., via discover_feeds).
    This skips provider discovery and crawling - just saves the feed record.
    Articles are fetched later via fetch_one/fetch_all.

    Args:
        feed_url: The URL of the feed to register.
        feed_name: Optional name. If not provided, URL is used as name.
        weight: Optional feed weight for semantic search ranking.
        feed_meta_data: Optional provider-specific metadata (e.g., selectors for WebpageProvider).
        refresh_interval: Optional refresh interval in seconds. Defaults to config value.

    Returns:
        Tuple of (saved Feed object, is_new).
    """
    import json as json_module

    from src.application.config import (
        get_default_feed_weight,
        get_default_refresh_interval,
    )
    from src.models import Feed

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
                            selectors=existing_meta["selectors"],
                        )
                except (json_module.JSONDecodeError, TypeError):
                    pass

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    feed = Feed(
        id=generate_feed_id(),
        name=feed_name or feed_url,
        url=feed_url,
        etag=None,
        modified_at=None,
        fetched_at=None,
        created_at=now,
        weight=weight if weight is not None else get_default_feed_weight(),
        metadata=feed_meta_data.to_json() if feed_meta_data else None,
        group=group,
        refresh_interval=refresh_interval
        if refresh_interval is not None
        else get_default_refresh_interval(),
    )
    return upsert_feed(feed)


def list_feeds() -> list[Feed]:
    """List all feeds with article counts.

    Returns:
        List of Feed objects with article counts available via articles_count attribute.
    """
    return storage_list_feeds()


def get_feed(feed_id: str) -> Feed | None:
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


def update_feed_metadata(
    feed_id: str,
    weight: float | None = None,
    group: str | None = None,
    feed_meta_data: FeedMetaData | None = None,
) -> tuple[Feed | None, bool]:
    """Update feed metadata (weight, group, metadata JSON).

    Args:
        feed_id: The ID of the feed to update.
        weight: Optional new weight (0.0-1.0).
        group: Optional new group name. Use empty string to clear.
        feed_meta_data: Optional FeedMetaData object to serialize as JSON.

    Returns:
        Tuple of (updated Feed object or None if not found, success bool).
    """
    metadata_str = feed_meta_data.to_json() if feed_meta_data else None
    return storage_update_feed_metadata(feed_id, weight, group, metadata_str)


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
        article_guid = _get_article_field(article, "guid") or generate_article_id(
            article
        )
        parsed_articles.append(
            {
                "guid": article_guid,
                "title": _get_article_field(article, "title") or "",
                "content": _get_article_field(article, "content") or "",
                "description": _get_article_field(article, "description") or "",
                "link": _get_article_field(article, "link") or "",
                "feed_id": feed.id,
                "published_at": _get_article_field(article, "published_at"),
            }
        )

    if not parsed_articles:
        return {"new_articles": 0}

    # Batch upsert all articles
    from src.storage.sqlite.impl import upsert_articles

    article_id_map = upsert_articles(parsed_articles)
    new_count = len(article_id_map)

    # Update feed metadata after successful fetch
    if new_count > 0:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
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
