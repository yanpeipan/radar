"""Feed management commands for Radar CLI."""

from __future__ import annotations

# Patch asyncio's executor shutdown timeout to avoid long hangs during cleanup.
# Python 3.13's shutdown_default_executor() waits up to 300 seconds for threads
# to finish, which causes CLI to hang after fetch completes. Reducing to 10 seconds.
import asyncio.constants
import logging
import sys
import time

import click
import uvloop

asyncio.constants.THREAD_JOIN_TIMEOUT = 10

from rich.console import Console  # noqa: E402

from src.application.feed import (  # noqa: E402
    get_feed,
    list_feeds,
    register_feed,
    remove_feed,
)
from src.cli.discover import _display_feeds  # noqa: E402
from src.cli.ui import (  # noqa: E402
    FetchProgress,
    format_discover_feeds,
    format_feed_list,
    print_json,
    print_json_error,
    print_summary,
)
from src.discovery import DiscoveredFeed, discover_feeds  # noqa: E402
from src.models import FeedMetaData  # noqa: E402

logger = logging.getLogger(__name__)


async def _fetch_with_progress(
    async_gen, total, description: str, concurrency: int = 10
):
    """Run async fetch with Rich progress bar. Returns (total_new, success_count, error_count, errors, elapsed_time)."""
    with FetchProgress(total, description, concurrency) as fp:
        async for result in async_gen:
            fp.update(result)
    return fp.total_new, fp.success_count, fp.error_count, fp.errors, fp.elapsed_time


def _get_provider_type(url: str) -> str:
    """Return "GitHub" if URL contains github.com, else "RSS"."""
    return "GitHub" if "github.com" in url.lower() else "RSS"


def _prompt_selection(feeds: list[DiscoveredFeed]) -> list[int]:
    """Prompt user to select feeds. Returns list of selected indices."""
    console = Console()

    click.secho("")
    click.secho("Select feeds to add:")
    click.secho("  a - Add all feeds")
    click.secho("  s - Select individually")
    click.secho("  c - Cancel")
    click.secho("")

    choice = console.input("Enter choice (a/s/c): ").strip().lower()

    if choice == "a":
        return list(range(len(feeds)))
    elif choice == "s":
        click.secho("Enter feed numbers (e.g., 1,3,5-7) or 'c' to cancel: ", fg="cyan")
        selection = console.input().strip()
        if selection.lower() == "c":
            return []
        return _parse_selection(selection, len(feeds))
    else:
        return []


def _parse_selection(selection: str, max_idx: int) -> list[int]:
    """Parse comma-separated numbers and ranges like '1,3,5-7' into indices."""
    indices = set()
    try:
        for part in selection.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                start, end = int(start.strip()), int(end.strip())
                for i in range(start, end + 1):
                    if 1 <= i <= max_idx:
                        indices.add(i - 1)
            else:
                i = int(part)
                if 1 <= i <= max_idx:
                    indices.add(i - 1)
        return sorted(indices)
    except ValueError:
        return []


def _get_webpage_selectors(url: str) -> list[str] | None:
    """Analyze page links and prompt user to select path patterns for filtering.

    Returns list of selected path prefixes, or None if questionary is not available.
    """
    from src.providers.webpage_provider import _analyze_link_paths

    try:
        import questionary
    except ModuleNotFoundError as e:
        click.secho(f"Error: Missing dependency - {e}", fg="red")
        click.secho("Install patchright: uv pip install patchright", fg="yellow")
        return None  # None means skip selector filtering entirely

    try:
        path_counts = _analyze_link_paths(url)
    except ModuleNotFoundError as e:
        click.secho(f"Error: Missing dependency - {e}", fg="red")
        click.secho("Install patchright: uv pip install patchright", fg="yellow")
        return None
    except Exception as e:
        click.secho(f"Warning: Could not analyze links: {e}", fg="yellow")
        return []

    if not path_counts:
        return []

    choices = [f"{path} ({count} links)" for path, count in path_counts.items()]
    selected = questionary.checkbox(
        "Select path patterns to filter (articles only):",
        choices=choices,
    ).ask()

    if not selected:
        return []

    # Extract path from "path (N links)" format
    result = []
    for choice in selected:
        path = choice.rsplit(" (", 1)[0]
        result.append(path)
    return result


from src.cli import cli  # noqa: E402


@cli.group()
@click.pass_context
def feed(ctx: click.Context) -> None:
    """Manage RSS/Atom feeds."""
    pass


@feed.command("add")
@click.argument("url")
@click.option(
    "--auto-discover/--no-auto-discover",
    default=True,
    help="Enable feed auto-discovery before adding (default: enabled)",
)
@click.option(
    "--automatic",
    default="off",
    type=click.Choice(["on", "off"]),
    help="Automatically add all discovered feeds (default: off)",
)
@click.option(
    "--discover-depth",
    default=1,
    type=click.IntRange(1, 10),
    help="Discovery crawl depth (default: 1)",
)
@click.option(
    "--weight",
    default=None,
    type=float,
    help="Feed weight for semantic search (default: 0.3)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def feed_add(
    ctx: click.Context,
    url: str,
    auto_discover: bool,
    automatic: str,
    discover_depth: int,
    weight: float | None,
    json_output: bool,
) -> None:
    """Add a new feed by URL (auto-detects provider type).

    Examples:

      feedship feed add example.com --auto-discover --automatic off
      feedship feed add example.com --automatic on
      feedship feed add nitter:elonmusk
      feedship feed add search:AI news
    """
    feeds: list = []
    result = None
    elapsed = 0.0

    # Check if URL is a pseudo-URL handled by providers (e.g., nitter:, search:, tavily:)
    from src.providers import discover as providers_discover

    provider_feeds = providers_discover(url)
    if provider_feeds:
        feeds = provider_feeds
        elapsed = 0.0
    else:
        # Regular URL - use discover_feeds for auto-discovery
        try:
            console = Console()
            start = time.time()
            with console.status(f"[cyan]Discovering feeds from {url}...") as _status:
                result = uvloop.run(discover_feeds(url, discover_depth, auto_discover))
                feeds = result.feeds
            elapsed = time.time() - start
        except Exception as e:
            if json_output:
                print_json_error(f"Discovery error: {e}", "discovery_error")
            click.secho(f"Discovery error: {e}", err=True, fg="red")
            sys.exit(1)

    if feeds and not json_output:
        click.secho(f"Discovered {len(feeds)} feed(s) in {elapsed:.1f}s", fg="cyan")
        if result and result.selectors:
            click.secho("Link selectors:", fg="cyan")
            for sel in sorted(result.selectors.values(), key=lambda x: -x.count):
                click.echo(f"  {sel.path} ({sel.count} links)")
                if sel.text:
                    click.echo(f"    text: {sel.text}")
                click.echo(f"    example: {sel.link}")

    # Automatic or selection
    if not feeds:
        if json_output:
            print_json({"feeds": [], "count": 0})
        else:
            click.secho("No feeds discovered.", fg="yellow")
        return

    if automatic == "on":
        added_count = 0
        updated_count = 0
        for feed in feeds:
            feed_meta = FeedMetaData(
                feed_type=feed.feed_type,
                selectors=feed.metadata.selectors if feed.metadata else None,
            )
            _, is_new = register_feed(feed.url, feed.title, weight, feed_meta)
            if is_new:
                added_count += 1
            else:
                updated_count += 1
        if json_output:
            print_json(
                {
                    "added": added_count,
                    "updated": updated_count,
                    "total": len(feeds),
                }
            )
            return
        if updated_count > 0:
            click.secho(
                f"Added {added_count}, updated {updated_count} feed(s).", fg="green"
            )
        else:
            click.secho(f"Added {added_count} feed(s) automatically.", fg="green")
        return

    # JSON mode with discovered feeds but not automatic
    if json_output:
        print_json(format_discover_feeds(feeds, elapsed))
        return

    # Show feed list and prompt for selection
    _display_feeds(feeds, numbered=True)
    selected = _prompt_selection(feeds)
    if not selected:
        click.secho("No feeds selected. Feed not added.", fg="yellow")
        return

    # Register selected feeds (no crawl - defer to background fetch)
    added_count = 0
    updated_count = 0
    for idx in selected:
        feed = feeds[idx]
        feed_meta = FeedMetaData(
            feed_type=feed.feed_type,
            selectors=feed.metadata.selectors if feed.metadata else None,
        )
        _, is_new = register_feed(feed.url, feed.title, weight, feed_meta)
        if is_new:
            added_count += 1
        else:
            updated_count += 1
    if updated_count > 0:
        click.secho(
            f"Added {added_count}, updated {updated_count} feed(s).", fg="green"
        )
    else:
        click.secho(f"Added {added_count} feed(s).", fg="green")


@feed.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def feed_list(ctx: click.Context, verbose: bool, json_output: bool) -> None:
    """List all subscribed feeds with provider type."""
    try:
        feeds = list_feeds()
        if not feeds:
            if json_output:
                print_json(format_feed_list([]))
                return
            click.secho("No feeds subscribed yet. Use 'feed add <url>' to add one.")
            return

        if json_output:
            print_json(format_feed_list(feeds))
            return

        from rich.console import Console
        from rich.table import Table

        console = Console()

        if verbose:
            for f in feeds:
                last_fetched = f.fetched_at or "Never"
                provider_type = _get_provider_type(f.url)
                articles_count = getattr(f, "articles_count", 0)
                weight = f.weight if f.weight is not None else 0.3

                table = Table(title=f.name, show_header=False, box=None, padding=(0, 1))
                table.add_column(style="cyan", no_wrap=True)
                table.add_column(style="white")
                table.add_row("ID", f.id)
                table.add_row("URL", f.url)
                table.add_row("Type", provider_type)
                table.add_row("Articles", str(articles_count))
                table.add_row("Weight", f"{weight:.1f}")
                table.add_row("Last Fetched", last_fetched)
                console.print(table)
                console.print()
        else:
            table = Table(
                title="[bold cyan]Feeds[/]",
                show_header=True,
                header_style="bold magenta",
                row_styles=["", "dim"],
            )
            table.add_column("Id", justify="right", style="cyan", no_wrap=True)
            table.add_column("Name", style="green", no_wrap=False)
            table.add_column("Type", style="yellow", no_wrap=True)
            table.add_column("Articles", justify="right", no_wrap=True)
            table.add_column("Weight", justify="right", no_wrap=True)
            table.add_column("Last Fetched", style="dim", no_wrap=True)

            for _i, f in enumerate(feeds, 1):
                last_fetched = f.fetched_at or "Never"
                if last_fetched != "Never":
                    last_fetched = last_fetched[:10]
                provider_type = _get_provider_type(f.url)
                articles_count = getattr(f, "articles_count", 0)
                weight = f.weight if f.weight is not None else 0.3

                table.add_row(
                    f.id,
                    f.name,
                    provider_type,
                    str(articles_count),
                    f"{weight:.1f}",
                    last_fetched,
                )

            console.print(table)
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to list feeds: {e}", "list_error")
        click.secho(f"Error: Failed to list feeds: {e}", err=True, fg="red")
        logger.exception("Failed to list feeds")
        sys.exit(1)


@feed.command("remove")
@click.argument("feed_id")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def feed_remove(ctx: click.Context, feed_id: str, json_output: bool) -> None:
    """Remove a feed by ID."""
    try:
        removed = remove_feed(feed_id)
        if removed:
            if json_output:
                print_json({"item": {"id": feed_id, "removed": True}})
            else:
                click.secho(f"Removed feed: {feed_id}", fg="green")
        else:
            if json_output:
                print_json_error("Feed not found", "not_found", exit_code=2)
            click.secho(f"Feed not found: {feed_id}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to remove feed: {e}", "remove_error")
        click.secho(f"Error: Failed to remove feed: {e}", err=True, fg="red")
        logger.exception("Failed to remove feed")
        sys.exit(1)


@cli.command("fetch")
@click.option("--all", "do_fetch_all", is_flag=True, help="Fetch all feeds")
@click.option(
    "--concurrency",
    default=10,
    type=click.IntRange(1, 100),
    help="Max concurrent fetches (default: 10)",
)
@click.argument("ids", nargs=-1, required=False)
@click.pass_context
def fetch(ctx: click.Context, do_fetch_all: bool, concurrency: int, ids: tuple) -> None:
    """Fetch new articles from subscribed feeds by ID.

    Examples:

      feedship fetch --all              Fetch all subscribed feeds

      feedship fetch <feed_id> [<feed_id>...]  Fetch specific feeds by ID
    """
    # Lazy import to avoid torch dependency for non-fetch commands
    from src.application.fetch import (
        fetch_all_async,
        fetch_ids_async,
        fetch_one_async_by_id,
    )

    # Case 1: ID arguments provided
    if ids:
        try:
            if len(ids) == 1:
                # Single ID: use async-native path for better performance
                feed_id = ids[0]
                feed = get_feed(feed_id)
                if not feed:
                    click.secho(f"Feed not found: {feed_id}", fg="yellow")
                    sys.exit(1)
                result = uvloop.run(fetch_one_async_by_id(feed_id))
                total_new = result.get("new_articles", 0)
                error = result.get("error")
                if error:
                    click.secho(f"Error fetching {feed.name}: {error}", fg="red")
                    sys.exit(1)
                click.secho(
                    f"Fetched {total_new} articles from {feed.name}", fg="green"
                )
            else:
                # Multiple IDs: use semaphore concurrency
                total_new, success_count, error_count, errors, elapsed = uvloop.run(
                    _fetch_with_progress(
                        fetch_ids_async(ids, concurrency),
                        len(ids),
                        f"[cyan]Fetching {len(ids)} feeds by ID (concurrency:{concurrency})...",
                        concurrency,
                    ),
                )
                print_summary(total_new, success_count, error_count, errors, elapsed)
        except Exception as e:
            click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
            logger.exception("Failed to fetch feeds")
            sys.exit(1)
        return

    # Case 2: --all flag
    if do_fetch_all:
        try:
            feeds = list_feeds()
            if not feeds:
                click.secho(
                    "No feeds subscribed. Use 'feed add <url>' to add one.", fg="yellow"
                )
                return
            total_new, success_count, error_count, errors, elapsed = uvloop.run(
                _fetch_with_progress(
                    fetch_all_async(concurrency=concurrency),
                    len(feeds),
                    f"[cyan]Fetching {len(feeds)} feeds (concurrency:{concurrency})...",
                    concurrency,
                ),
            )
            print_summary(
                total_new, success_count, error_count, errors, elapsed, prefix="✓ "
            )
        except Exception as e:
            click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
            logger.exception("Failed to fetch feeds")
            sys.exit(1)
        return

    # Case 3: No arguments
    click.secho("Use --all to fetch all feeds: feedship fetch --all")
    click.secho("Or specify feed IDs to fetch: feedship fetch <feed_id> [<feed_id>...]")
