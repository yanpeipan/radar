"""Tag management use cases - apply and remove tags on feeds."""

from __future__ import annotations

from src.models import Tag
from src.storage import assign_tag_to_feed as storage_assign_tag_to_feed
from src.storage import get_feed as storage_get_feed
from src.storage import remove_tag_from_feed as storage_remove_tag_from_feed
from src.storage import get_tags_for_feed as storage_get_tags_for_feed


class FeedNotFoundError(Exception):
    """Raised when a feed is not found in the database."""


def add_tag_to_feed(feed_id: str, tag_name: str) -> Tag:
    """Assign a tag to a feed by name, creating the tag if it does not exist.

    Args:
        feed_id: The ID of the feed to tag.
        tag_name: The name of the tag to assign.

    Returns:
        The Tag object that was assigned.

    Raises:
        FeedNotFoundError: If the feed does not exist.
    """
    feed = storage_get_feed(feed_id)
    if not feed:
        raise FeedNotFoundError(f"Feed not found: {feed_id}")

    return storage_assign_tag_to_feed(feed_id, tag_name)


def remove_tag_from_feed(feed_id: str, tag_name: str) -> bool:
    """Remove a tag assignment from a feed by name.

    Args:
        feed_id: The ID of the feed to untag.
        tag_name: The name of the tag to remove.

    Returns:
        True if the assignment was removed, False if the tag was not assigned.

    Raises:
        FeedNotFoundError: If the feed does not exist.
    """
    feed = storage_get_feed(feed_id)
    if not feed:
        raise FeedNotFoundError(f"Feed not found: {feed_id}")

    return storage_remove_tag_from_feed(feed_id, tag_name)


def list_feed_tags(feed_id: str) -> list[Tag]:
    """List all tags assigned to a feed.

    Args:
        feed_id: The ID of the feed.

    Returns:
        List of Tag objects assigned to the feed, ordered by name.

    Raises:
        FeedNotFoundError: If the feed does not exist.
    """
    feed = storage_get_feed(feed_id)
    if not feed:
        raise FeedNotFoundError(f"Feed not found: {feed_id}")

    return storage_get_tags_for_feed(feed_id)
