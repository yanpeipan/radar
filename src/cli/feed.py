"""Feed management commands for RSS reader CLI."""

import sys
import logging

import click
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

from src.application.feed import (
    FeedNotFoundError,
    add_feed,
    get_feed,
    list_feeds,
    remove_feed,
    fetch_one,
)
import uvloop
from src.discovery import discover_feeds, DiscoveredFeed
from src.cli.discover import _display_feeds

logger = logging.getLogger(__name__)


async def _fetch_with_progress(async_gen, total, description):
    """Run async fetch with Rich progress bar. Returns (total_new, success_count, error_count, errors)."""
    total_new = 0
    success_count = 0
    error_count = 0
    errors = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(description, total=total)

        async for result in async_gen:
            if result["new_articles"] > 0:
                total_new += result["new_articles"]
                success_count += 1
                progress.update(task, advance=1, description=f"[green]{result.get('feed_name', result.get('feed_id'))}: +{result['new_articles']}")
            elif result.get("error"):
                error_count += 1
                errors.append(f"{result.get('feed_name', result.get('feed_id'))}: {result['error']}")
                progress.update(task, advance=1, description=f"[red]{result.get('feed_name', result.get('feed_id'))}: error")
            else:
                success_count += 1
                progress.update(task, advance=1, description=f"[blue]{result.get('feed_name', result.get('feed_id'))}: up to date")

    return total_new, success_count, error_count, errors


def _print_fetch_summary(total_new, success_count, error_count, errors, prefix=""):
    """Print fetch result summary."""
    click.secho("")
    if error_count == 0:
        click.secho(f"{prefix}Fetched {total_new} articles from {success_count} feed(s)", fg="green")
    else:
        click.secho(f"{prefix}Fetched {total_new} articles from {success_count} feed(s), {error_count} errors", fg="yellow")
        for err in errors:
            click.secho(f"  - {err}", fg="red")


def _get_provider_type(url: str) -> str:
    """Return "GitHub" if URL contains github.com, else "RSS"."""
    return "GitHub" if "github.com" in url.lower() else "RSS"


def _prompt_selection(feeds: list[DiscoveredFeed]) -> list[int]:
    """Prompt user to select feeds. Returns list of selected indices."""
    from rich.console import Console
    console = Console()

    click.secho("")
    click.secho("Select feeds to add:")
    click.secho("  a - Add all feeds")
    click.secho("  s - Select individually")
    click.secho("  c - Cancel")
    click.secho("")

    choice = console.input("Enter choice (a/s/c): ").strip().lower()

    if choice == "a":
        # Add all
        return list(range(len(feeds)))
    elif choice == "s":
        # Individual selection
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
                        indices.add(i - 1)  # Convert to 0-based
            else:
                i = int(part)
                if 1 <= i <= max_idx:
                    indices.add(i - 1)
        return sorted(list(indices))
    except ValueError:
        return []


from src.cli import cli


@cli.group()
@click.pass_context
def feed(ctx: click.Context) -> None:
    """Manage RSS/Atom feeds."""
    pass


@feed.command("add")
@click.argument("url")
@click.option(
    "--discover",
    default="on",
    type=click.Choice(["on", "off"]),
    help="Enable feed discovery before adding (default: on)",
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
@click.pass_context
def feed_add(ctx: click.Context, url: str, discover: str, automatic: str, discover_depth: int) -> None:
    """Add a new feed by URL (auto-detects provider type).

    Examples:

      rss-reader feed add example.com --discover on --automatic off
      rss-reader feed add example.com --automatic on
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose")

    if discover == "on":
        # Run discovery first
        try:
            feeds = uvloop.run(discover_feeds(url, discover_depth))
        except Exception as e:
            click.secho(f"Error during discovery: {e}", err=True, fg="red")
            sys.exit(1)

        if not feeds:
            click.secho(
                f"No feeds found at {url}. Try providing a website URL instead of a feed URL.",
                err=True,
                fg="yellow",
            )
            sys.exit(1)

        if automatic == "on":
            # Auto-add all discovered feeds
            added_count = 0
            for feed in feeds:
                try:
                    add_feed(feed.url)
                    added_count += 1
                except ValueError as e:
                    # Feed already exists or failed
                    click.secho(f"  Skipped {feed.url}: {e}", fg="yellow")
            click.secho(f"Added {added_count} feed(s) automatically.", fg="green")
            return

        # Single feed: auto-add without prompting
        if len(feeds) == 1:
            feed = feeds[0]
            try:
                add_feed(feed.url)
                click.secho(f"Added feed: {feed.url}", fg="green")
            except ValueError as e:
                click.secho(f"  Skipped {feed.url}: {e}", fg="yellow")
            return

        # Multiple feeds: show numbered list and prompt for selection
        _display_feeds(feeds, numbered=True)
        selected = _prompt_selection(feeds)
        if not selected:
            click.secho("No feeds selected. Feed not added.", fg="yellow")
            return

        # Add selected feeds
        added_count = 0
        for idx in selected:
            feed = feeds[idx]
            try:
                add_feed(feed.url)
                added_count += 1
            except ValueError as e:
                click.secho(f"  Skipped {feed.url}: {e}", fg="yellow")
        click.secho(f"Added {added_count} feed(s).", fg="green")
        return

    # Original behavior when --discover off
    try:
        feed_obj = add_feed(url)

        # Determine provider type for display
        from src.providers import discover_or_default
        providers = discover_or_default(url)
        if providers:
            provider_name = providers[0].__class__.__name__.replace("Provider", "")
        else:
            provider_name = "Unknown"

        click.secho(f"Added feed: {feed_obj.name} ({provider_name})", fg="green")
        if verbose:
            click.secho(f"Feed ID: {feed_obj.id}")
            click.secho(f"Provider: {provider_name}")
    except ValueError as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to add feed: {e}", err=True, fg="red")
        logger.exception("Failed to add feed")
        sys.exit(1)


@feed.command("list")
@click.pass_context
def feed_list(ctx: click.Context) -> None:
    """List all subscribed feeds with provider type."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        feeds = list_feeds()
        if not feeds:
            click.secho("No feeds subscribed yet. Use 'feed add <url>' to add one.")
            return

        if verbose:
            # Verbose output
            click.secho("ID  | Name | URL | Provider | Articles | Last Fetched")
            click.secho("-" * 90)
            for f in feeds:
                last_fetched = f.last_fetched or "Never"
                provider_type = _get_provider_type(f.url)
                click.secho(
                    f"{f.id}\n"
                    f"  Name: {f.name}\n"
                    f"  URL: {f.url}\n"
                    f"  Provider: {provider_type}\n"
                    f"  Articles: {getattr(f, 'articles_count', 0)}\n"
                    f"  Last Fetched: {last_fetched}"
                )
        else:
            # Compact table output
            click.secho("ID  | Name | URL | Type | Articles | Last Fetched")
            click.secho("-" * 90)
            for f in feeds:
                last_fetched = f.last_fetched or "Never"
                provider_type = _get_provider_type(f.url)
                click.secho(
                    f"{f.id} | {f.name[:30]} | {f.url[:40]} | {provider_type} | "
                    f"{getattr(f, 'articles_count', 0)} | {last_fetched[:10]}"
                )
    except Exception as e:
        click.secho(f"Error: Failed to list feeds: {e}", err=True, fg="red")
        logger.exception("Failed to list feeds")
        sys.exit(1)


@feed.command("remove")
@click.argument("feed_id")
@click.pass_context
def feed_remove(ctx: click.Context, feed_id: str) -> None:
    """Remove a feed by ID."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        removed = remove_feed(feed_id)
        if removed:
            click.secho(f"Removed feed: {feed_id}", fg="green")
        else:
            click.secho(f"Feed not found: {feed_id}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to remove feed: {e}", err=True, fg="red")
        logger.exception("Failed to remove feed")
        sys.exit(1)


@cli.command("fetch")
@click.option("--all", "do_fetch_all", is_flag=True, help="Fetch all feeds")
@click.option("--concurrency", default=10, type=click.IntRange(1, 100), help="Max concurrent fetches (default: 10)")
@click.argument("ids", nargs=-1, required=False)
@click.pass_context
def fetch(ctx: click.Context, do_fetch_all: bool, concurrency: int, ids: tuple) -> None:
    """Fetch new articles from subscribed feeds by ID.

    Examples:

      rss-reader fetch --all              Fetch all subscribed feeds

      rss-reader fetch <feed_id> [<feed_id>...]  Fetch specific feeds by ID
    """
    # Lazy import to avoid torch dependency for non-fetch commands
    from src.application.fetch import fetch_all_async, fetch_ids_async, fetch_one_async_by_id

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
                click.secho(f"Fetched {total_new} articles from {feed.name}", fg="green")
            else:
                # Multiple IDs: use semaphore concurrency
                total_new, success_count, error_count, errors = uvloop.run(
                    _fetch_with_progress(fetch_ids_async(ids, concurrency), len(ids), f"[cyan]Fetching {len(ids)} feeds by ID...")
                )
                _print_fetch_summary(total_new, success_count, error_count, errors)
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
                click.secho("No feeds subscribed. Use 'feed add <url>' to add one.", fg="yellow")
                return
            total_new, success_count, error_count, errors = uvloop.run(
                _fetch_with_progress(fetch_all_async(concurrency=concurrency), len(feeds), f"[cyan]Fetching {len(feeds)} feeds...")
            )
            _print_fetch_summary(total_new, success_count, error_count, errors, prefix="✓ ")
        except Exception as e:
            click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
            logger.exception("Failed to fetch feeds")
            sys.exit(1)
        return

    # Case 3: No arguments
    click.secho("Use --all to fetch all feeds: rss-reader fetch --all")
    click.secho("Or specify feed IDs to fetch: rss-reader fetch <feed_id> [<feed_id>...]")
