"""Unified Rich progress bar and elapsed time statistics for src.cli commands."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

if TYPE_CHECKING:
    from src.application.articles import ArticleListItem
    from src.discovery import DiscoveredFeed
    from src.models import Feed


class FetchProgress:
    """Context manager for feed fetch operations with Rich progress bar.

    Usage:
        with FetchProgress(total, description, concurrency) as fp:
            async for result in async_gen:
                fp.update(result)
        print(fp.total_new, fp.success_count, fp.elapsed_time)
    """

    def __init__(self, total: int, description: str, concurrency: int = 10):
        """Initialize fetch progress tracker.

        Args:
            total: Total number of feeds to fetch.
            description: Initial progress bar description.
            concurrency: Max concurrent fetches (shown in description).
        """
        self._total = total
        self._concurrency = concurrency
        self._description = description
        self._progress: Progress | None = None
        self._task = None
        self._start_time: float = 0
        self._total_new = 0
        self._success_count = 0
        self._error_count = 0
        self._errors: list[str] = []

    def __enter__(self) -> FetchProgress:
        """Enter context manager, start progress bar."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        )
        self._progress.__enter__()
        self._task = self._progress.add_task(self._description, total=self._total)
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, close progress bar."""
        if self._progress:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, result: dict) -> None:
        """Update progress after each feed result.

        Args:
            result: Dict with keys: feed_name/feed_id, new_articles, error (optional).
        """
        if not self._progress or self._task is None:
            return

        feed_name = result.get("feed_name", result.get("feed_id", "?"))
        if result.get("new_articles", 0) > 0:
            self._total_new += result["new_articles"]
            self._success_count += 1
            self._progress.update(
                self._task,
                advance=1,
                description=f"[green]{feed_name}: +{result['new_articles']}",
            )
        elif result.get("error"):
            self._error_count += 1
            self._errors.append(f"{feed_name}: {result['error']}")
            self._progress.update(
                self._task,
                advance=1,
                description=f"[red]{feed_name}: error",
            )
        else:
            self._success_count += 1
            self._progress.update(
                self._task,
                advance=1,
                description=f"[blue]{feed_name}: up to date",
            )

    @property
    def elapsed_time(self) -> float:
        """Elapsed time in seconds since context entry."""
        return time.time() - self._start_time

    @property
    def total_new(self) -> int:
        """Total new articles fetched."""
        return self._total_new

    @property
    def success_count(self) -> int:
        """Number of successfully fetched feeds."""
        return self._success_count

    @property
    def error_count(self) -> int:
        """Number of feeds with errors."""
        return self._error_count

    @property
    def errors(self) -> list[str]:
        """List of error messages."""
        return self._errors


class DiscoverProgress:
    """Context manager for discover operations with Rich progress bar.

    Usage:
        with DiscoverProgress("Discovering feeds...") as dp:
            for feed in feeds:
                dp.update(feed)
        print(dp.feeds_found, dp.elapsed_time)
    """

    def __init__(self, description: str):
        """Initialize discover progress tracker.

        Args:
            description: Initial progress bar description.
        """
        self._description = description
        self._progress: Progress | None = None
        self._task = None
        self._start_time: float = 0
        self._feeds_found = 0

    def __enter__(self) -> DiscoverProgress:
        """Enter context manager, start progress bar."""
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        )
        self._progress.__enter__()
        self._task = self._progress.add_task(self._description, total=None)
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, close progress bar."""
        if self._progress:
            self._progress.__exit__(exc_type, exc_val, exc_tb)

    def update(self, feed: DiscoveredFeed) -> None:
        """Update progress after each feed discovered.

        Args:
            feed: DiscoveredFeed object found.
        """
        if not self._progress or self._task is None:
            return

        self._feeds_found += 1
        feed_name = feed.title or feed.url
        self._progress.update(
            self._task,
            description=f"[green]{feed_name} ({feed.feed_type})",
        )

    @property
    def elapsed_time(self) -> float:
        """Elapsed time in seconds since context entry."""
        return time.time() - self._start_time

    @property
    def feeds_found(self) -> int:
        """Number of feeds discovered."""
        return self._feeds_found


def print_summary(
    total_new: int,
    success_count: int,
    error_count: int,
    errors: list[str],
    elapsed_time: float,
    prefix: str = "",
) -> None:
    """Print fetch result summary with elapsed time.

    Args:
        total_new: Total new articles fetched.
        success_count: Number of successful feeds.
        error_count: Number of failed feeds.
        errors: List of error message strings.
        elapsed_time: Elapsed time in seconds.
        prefix: Optional prefix like "✓ ".
    """
    click.secho("")
    elapsed_str = f" in {elapsed_time:.1f}s" if elapsed_time > 0 else ""
    if error_count == 0:
        click.secho(
            f"{prefix}Fetched {total_new} articles from {success_count} feed(s){elapsed_str}",
            fg="green",
        )
    else:
        click.secho(
            f"{prefix}Fetched {total_new} articles from {success_count} feed(s), "
            f"{error_count} errors{elapsed_str}",
            fg="yellow",
        )
        for err in errors:
            click.secho(f"  - {err}", fg="red")


# =============================================================================
# JSON Output Utilities
# =============================================================================


def print_json(data: dict) -> None:
    """Print data as formatted JSON using Rich.

    Args:
        data: Dictionary to print as JSON.
    """
    console = Console()
    console.print_json(data=data)


def _iso_timestamp(value: int | str | None) -> str | None:
    """Convert unix timestamp int to ISO 8601 string.

    Args:
        value: Unix timestamp int, ISO string, or None.

    Returns:
        ISO 8601 formatted string, original string, or None.
    """
    if value is None:
        return None
    if isinstance(value, int):
        dt = datetime.utcfromtimestamp(value)
        return dt.isoformat() + "Z"
    return value


def _serialize_article(item: ArticleListItem) -> dict:
    """Serialize ArticleListItem to dict with ISO 8601 timestamps.

    Args:
        item: ArticleListItem to serialize.

    Returns:
        Dictionary with serialized article fields.
    """
    return {
        "id": item.id,
        "feed_id": item.feed_id,
        "feed_name": item.feed_name,
        "title": item.title,
        "link": item.link,
        "guid": item.guid,
        "published_at": _iso_timestamp(item.published_at),
        "description": item.description,
        "score": item.score,
        "quality_score": item.quality_score,
    }


def _serialize_feed(feed: Feed) -> dict:
    """Serialize Feed object to dict with ISO 8601 timestamps.

    Args:
        feed: Feed object to serialize.

    Returns:
        Dictionary with serialized feed fields.
    """
    return {
        "id": feed.id,
        "name": feed.name,
        "url": feed.url,
        "fetched_at": _iso_timestamp(feed.fetched_at) if feed.fetched_at else None,
        "created_at": _iso_timestamp(feed.created_at) if feed.created_at else None,
        "weight": feed.weight,
        "refresh_interval": feed.refresh_interval,
    }


def _serialize_discovered_feed(feed: DiscoveredFeed) -> dict:
    """Serialize DiscoveredFeed to dict.

    Args:
        feed: DiscoveredFeed to serialize.

    Returns:
        Dictionary with type, title, and url.
    """
    return {
        "type": feed.feed_type.value
        if hasattr(feed.feed_type, "value")
        else feed.feed_type,
        "title": feed.title,
        "url": feed.url,
    }


def format_article_list(items: list[ArticleListItem], limit: int) -> dict:
    """Format article list for JSON output.

    Args:
        items: List of ArticleListItem objects.
        limit: Maximum number requested.

    Returns:
        Dict with items, count, limit, and has_more flag.
    """
    return {
        "items": [_serialize_article(item) for item in items],
        "count": len(items),
        "limit": limit,
        "has_more": len(items) >= limit,
    }


def format_article_item(article: dict) -> dict:
    """Format single article detail for JSON output.

    Args:
        article: Article dict from get_article_detail.

    Returns:
        Dict with item wrapper containing serialized article.
    """
    serialized = dict(article)
    if "published_at" in serialized:
        serialized["published_at"] = _iso_timestamp(serialized["published_at"])
    return {"item": serialized}


def format_feed_list(feeds: list[Feed]) -> dict:
    """Format feed list for JSON output.

    Args:
        feeds: List of Feed objects.

    Returns:
        Dict with items and count.
    """
    return {
        "items": [_serialize_feed(feed) for feed in feeds],
        "count": len(feeds),
    }


def format_feed_item(feed: Feed) -> dict:
    """Format single feed for JSON output.

    Args:
        feed: Feed object.

    Returns:
        Dict with item wrapper containing serialized feed.
    """
    return {"item": _serialize_feed(feed)}


def format_discover_feeds(feeds: list[DiscoveredFeed], elapsed: float) -> dict:
    """Format discovered feeds for JSON output.

    Args:
        feeds: List of DiscoveredFeed objects.
        elapsed: Elapsed time in seconds.

    Returns:
        Dict with feeds list, count, and elapsed_seconds.
    """
    return {
        "feeds": [_serialize_discovered_feed(feed) for feed in feeds],
        "count": len(feeds),
        "elapsed_seconds": round(elapsed, 2),
    }


def format_fetch_results(
    feeds: list[dict],
    total_new: int,
    success_count: int,
    error_count: int,
    elapsed: float,
) -> dict:
    """Format fetch results for JSON output.

    Args:
        feeds: List of feed result dicts with feed_name, feed_id, new_articles, error.
        total_new: Total new articles across all feeds.
        success_count: Number of successfully fetched feeds.
        error_count: Number of feeds with errors.
        elapsed: Elapsed time in seconds.

    Returns:
        Dict with feeds list and summary statistics.
    """
    return {
        "feeds": feeds,
        "total_new": total_new,
        "success_count": success_count,
        "error_count": error_count,
        "elapsed_seconds": round(elapsed, 2),
    }


def print_json_error(message: str, code: str, exit_code: int = 1) -> None:
    """Print error as JSON and exit.

    Args:
        message: Error message.
        code: Error code string.
        exit_code: Exit code to use (default 1).
    """
    print_json({"error": message, "code": code})
    sys.exit(exit_code)
