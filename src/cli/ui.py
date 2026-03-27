"""Unified Rich progress bar and elapsed time statistics for src.cli commands."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import click
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

if TYPE_CHECKING:
    from src.discovery import DiscoveredFeed


class FetchProgress:
    """Context manager for feed fetch operations with Rich progress bar.

    Usage:
        with FetchProgress(total, description) as fp:
            async for result in async_gen:
                fp.update(result)
        print(fp.total_new, fp.success_count, fp.elapsed_time)
    """

    def __init__(self, total: int, description: str):
        """Initialize fetch progress tracker.

        Args:
            total: Total number of feeds to fetch.
            description: Initial progress bar description.
        """
        self._total = total
        self._description = description
        self._progress: Progress | None = None
        self._task = None
        self._start_time: float = 0
        self._total_new = 0
        self._success_count = 0
        self._error_count = 0
        self._errors: list[str] = []

    def __enter__(self) -> "FetchProgress":
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

    def __enter__(self) -> "DiscoverProgress":
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

    def update(self, feed: "DiscoveredFeed") -> None:
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
            f"{error_count} errors(elapsed_str)",
            fg="yellow",
        )
        for err in errors:
            click.secho(f"  - {err}", fg="red")
