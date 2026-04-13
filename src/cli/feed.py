"""Feed management commands for Radar CLI."""

from __future__ import annotations

# Patch asyncio's executor shutdown timeout to avoid long hangs during cleanup.
# Python 3.13's shutdown_default_executor() waits up to 300 seconds for threads
# to finish, which causes CLI to hang after fetch completes. Reducing to 10 seconds.
import asyncio.constants
import cProfile
import io
import logging
import pstats
import sys
import time
from pathlib import Path

import click
import uvloop

asyncio.constants.THREAD_JOIN_TIMEOUT = 10

from rich.console import Console  # noqa: E402

from src.application.feed import (  # noqa: E402
    get_feed,
    list_feeds,
    register_feed,
    remove_feed,
    update_feed_metadata,
)
from src.application.opml import export_feeds_to_opml  # noqa: E402
from src.cli.ui import (  # noqa: E402
    FetchProgress,
    format_discover_feeds,
    format_feed_list,
    format_fetch_results,
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
    import questionary

    # Auto-select single feed - no prompt needed for common case
    if len(feeds) == 1:
        return [0]

    # Build feed choices for checkbox - use URL as unique identifier
    feed_choices = [feed.url for feed in feeds]
    selected = questionary.checkbox(
        "Select feeds to add (space to toggle):",
        choices=feed_choices,
        style=questionary.Style(
            [
                ("selected", "bold cyan"),
                ("checkbox", "cyan"),
            ]
        ),
    ).ask()
    if not selected or selected is None:
        return []
    # Map selected URLs back to indices
    selected_set = set(selected)
    return [i for i, feed in enumerate(feeds) if feed.url in selected_set]


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
@click.option(
    "--group",
    default=None,
    type=str,
    help="Group name for organizing feeds (max 100 chars)",
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
    group: str | None,
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
                return
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
        added_urls = []
        for feed in feeds:
            feed_meta = FeedMetaData(
                feed_type=feed.feed_type.value
                if hasattr(feed.feed_type, "value")
                else feed.feed_type,
                selectors=feed.metadata.selectors if feed.metadata else None,
            )
            _, is_new = register_feed(feed.url, feed.title, weight, feed_meta, group)
            if is_new:
                added_count += 1
                added_urls.append(feed.url)
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
            if added_count == 1:
                click.secho(
                    f"Added {added_count} feed(s) automatically: {added_urls[0]}",
                    fg="green",
                )
            else:
                click.secho(f"Added {added_count} feed(s) automatically.", fg="green")
        return

    # JSON mode with discovered feeds but not automatic
    if json_output:
        print_json(format_discover_feeds(feeds, elapsed))
        return

    # Show feed list and prompt for selection
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
            feed_type=feed.feed_type.value
            if hasattr(feed.feed_type, "value")
            else feed.feed_type,
            selectors=feed.metadata.selectors if feed.metadata else None,
        )
        _, is_new = register_feed(feed.url, feed.title, weight, feed_meta, group)
        if is_new:
            added_count += 1
        else:
            updated_count += 1
    if updated_count > 0:
        click.secho(
            f"Added {added_count}, updated {updated_count} feed(s).", fg="green"
        )
    else:
        if added_count == 1 and len(selected) == 1:
            # Show URL for single feed add
            click.secho(
                f"Added {added_count} feed(s): {feeds[selected[0]].url}", fg="green"
            )
        else:
            click.secho(f"Added {added_count} feed(s).", fg="green")


@feed.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--group",
    default=None,
    type=str,
    help="Filter feeds by group (exact match)",
)
@click.pass_context
def feed_list(
    ctx: click.Context, verbose: bool, json_output: bool, group: str | None
) -> None:
    """List all subscribed feeds with provider type."""
    try:
        feeds = list_feeds()

        # Filter by group if specified
        if group is not None:
            if group == "" or group.lower() == "none":
                # Show ungrouped feeds
                feeds = [f for f in feeds if f.group is None]
            else:
                # Exact match filter
                feeds = [f for f in feeds if f.group == group]

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
                table.add_row("Group", f.group or "Ungrouped")
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
            table.add_column("Group", style="dim", no_wrap=True)
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
                    f.group or "",
                    last_fetched,
                )

            console.print(table)
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to list feeds: {e}", "list_error")
            return
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
            return
        click.secho(f"Error: Failed to remove feed: {e}", err=True, fg="red")
        logger.exception("Failed to remove feed")
        sys.exit(1)


@feed.command("update")
@click.argument("feed_id")
@click.option("--weight", default=None, type=float, help="Feed weight (0.0-1.0)")
@click.option(
    "--group", default=None, type=str, help="Group name (use empty string to clear)"
)
@click.option(
    "--feed-type",
    "feed_type",
    default=None,
    type=str,
    help="Feed type (rss, atom, webpage, etc.)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def feed_update(
    ctx: click.Context,
    feed_id: str,
    weight: float | None,
    group: str | None,
    feed_type: str | None,
    json_output: bool,
) -> None:
    """Update feed metadata (weight, group, feed-type).

    Examples:

      feedship feed update abc123 --weight 0.5
      feedship feed update abc123 --group AI
      feedship feed update abc123 --feed-type rss
      feedship feed update abc123 --weight 0.8 --group Tech --feed-type atom
    """
    try:
        # Check feed exists
        feed = get_feed(feed_id)
        if not feed:
            if json_output:
                print_json_error("Feed not found", "not_found", exit_code=2)
            click.secho(f"Feed not found: {feed_id}", fg="yellow")
            sys.exit(1)

        # Build FeedMetaData if feed_type is provided
        feed_meta_data = None
        if feed_type is not None:
            # Preserve existing selectors from current metadata
            current_meta = feed.metadata_parsed if feed.metadata else None
            existing_selectors = current_meta.selectors if current_meta else None
            feed_meta_data = FeedMetaData(
                feed_type=feed_type, selectors=existing_selectors
            )

        # Call application layer
        updated_feed, success = update_feed_metadata(
            feed_id, weight=weight, group=group, feed_meta_data=feed_meta_data
        )

        if not success:
            if json_output:
                print_json_error("Failed to update feed", "update_error")
            click.secho("Failed to update feed", fg="red")
            sys.exit(1)

        if json_output:
            print_json(
                {
                    "item": {
                        "id": updated_feed.id,
                        "name": updated_feed.name,
                        "weight": updated_feed.weight,
                        "group": updated_feed.group,
                        "metadata": updated_feed.metadata,
                        "updated": True,
                    }
                }
            )
        else:
            click.secho(f"Updated feed: {updated_feed.name}", fg="green")
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to update feed: {e}", "update_error")
            return
        click.secho(f"Error: Failed to update feed: {e}", err=True, fg="red")
        logger.exception("Failed to update feed")
        sys.exit(1)


@feed.command("export")
@click.option("--opml", "as_opml", is_flag=True, help="Export feeds as OPML 2.0 XML")
@click.option(
    "--output",
    "-o",
    "output_file",
    default=None,
    type=click.Path(dir_okay=False, writable=True),
    help="Output file path (default: stdout)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def feed_export(
    ctx: click.Context,
    as_opml: bool,
    output_file: str | None,
    json_output: bool,
) -> None:
    """Export subscribed feeds.

    Examples:

      feedship feed export --opml                  Export all feeds as OPML to stdout
      feedship feed export --opml -o feeds.opml    Export to file
    """
    try:
        feeds = list_feeds()

        if not feeds:
            if json_output:
                print_json({"feeds": [], "count": 0})
            else:
                click.secho("No feeds to export.", fg="yellow")
            return

        if not as_opml:
            if json_output:
                print_json(format_feed_list(feeds))
            else:
                click.secho("Use --opml to export feeds as OPML 2.0 XML.", fg="yellow")
            return

        opml_xml = export_feeds_to_opml(feeds)

        if output_file:
            Path(output_file).write_text(opml_xml, encoding="utf-8")
            if json_output:
                print_json({"file": output_file, "count": len(feeds), "exported": True})
            else:
                click.secho(
                    f"Exported {len(feeds)} feed(s) to {output_file}", fg="green"
                )
        else:
            click.echo(opml_xml)
            if json_output:
                # Already output OPML to stdout, print summary as JSON too
                print_json({"count": len(feeds), "format": "opml"})
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to export feeds: {e}", "export_error")
            return
        click.secho(f"Error: Failed to export feeds: {e}", err=True, fg="red")
        logger.exception("Failed to export feeds")
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
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--profile",
    is_flag=True,
    help="Enable cProfile profiling, output to profiles/ directory",
)
@click.option(
    "--url",
    "url_to_fetch",
    type=str,
    help="Fetch articles directly from URL without saving to database",
)
@click.pass_context
def fetch(
    ctx: click.Context,
    do_fetch_all: bool,
    concurrency: int,
    ids: tuple,
    json_output: bool,
    profile: bool,
    url_to_fetch: str | None,
) -> None:
    """Fetch new articles from subscribed feeds by ID.

    Examples:

      feedship fetch --all              Fetch all subscribed feeds

      feedship fetch <feed_id> [<feed_id>...]  Fetch specific feeds by ID
    """
    # Lazy import to avoid torch dependency for non-fetch commands
    from dataclasses import asdict

    from src.application.fetch import (
        fetch_all_async,
        fetch_ids_async,
        fetch_one_async_by_id,
    )
    from src.models import Feed
    from src.providers import match_first

    def _do_fetch() -> None:
        """Main fetch logic extracted for profiling support."""
        # Case 0: --url option (fetch directly without saving to DB)
        if url_to_fetch:
            # Mutual exclusivity check: --url and IDs cannot be used together
            if ids:
                if json_output:
                    print_json_error("Cannot use --url with --id", "mutual_exclusion")
                click.secho("Cannot use --url with --id", fg="red", err=True)
                sys.exit(1)

            # Find provider for URL
            provider = match_first(url_to_fetch)
            if not provider:
                if json_output:
                    print_json_error("No provider found for this URL", "no_provider")
                click.secho("No provider found for this URL", fg="red", err=True)
                sys.exit(1)

            # Create minimal Feed object for provider
            feed = Feed(
                id="__url_fetch__",
                name=url_to_fetch,
                url=url_to_fetch,
                created_at="",
            )

            # Fetch articles directly from provider
            try:
                result = provider.fetch_articles(feed)
                articles = result.articles

                if json_output:
                    print_json(
                        {
                            "articles": [asdict(a) for a in articles],
                            "count": len(articles),
                        }
                    )
                else:
                    if articles:
                        click.secho(
                            f"Fetched {len(articles)} articles from {url_to_fetch}",
                            fg="green",
                        )
                    else:
                        click.secho(
                            f"No articles found for {url_to_fetch}",
                            fg="yellow",
                        )
                return
            except Exception as e:
                if json_output:
                    print_json_error(f"Failed to fetch from URL: {e}", "fetch_error")
                click.secho(f"Error: Failed to fetch from URL: {e}", err=True, fg="red")
                logger.exception("Failed to fetch from URL")
                sys.exit(1)

        # Case 1: ID arguments provided
        if ids:
            try:
                if len(ids) == 1:
                    # Single ID: use async-native path for better performance
                    feed_id = ids[0]
                    feed = get_feed(feed_id)
                    if not feed:
                        if json_output:
                            print_json_error(f"Feed not found: {feed_id}", "not_found")
                        click.secho(f"Feed not found: {feed_id}", fg="yellow")
                        sys.exit(1)
                    result = uvloop.run(fetch_one_async_by_id(feed_id))
                    total_new = result.get("new_articles", 0)
                    error = result.get("error")
                    if error:
                        if json_output:
                            print_json_error(
                                f"Error fetching {feed.name}: {error}", "fetch_error"
                            )
                        click.secho(f"Error fetching {feed.name}: {error}", fg="red")
                        sys.exit(1)
                    if json_output:
                        print_json(
                            {
                                "feed": {
                                    "feed_name": feed.name,
                                    "feed_id": feed.id,
                                    "new_articles": total_new,
                                },
                                "elapsed_seconds": 0.0,
                            }
                        )
                    else:
                        click.secho(
                            f"Fetched {total_new} articles from {feed.name}", fg="green"
                        )
                else:
                    # Multiple IDs: use semaphore concurrency
                    if json_output:
                        # JSON mode: skip progress bar
                        import time

                        async def _collect_json():
                            results = []
                            async for r in fetch_ids_async(ids, concurrency):
                                results.append(r)
                            return results

                        start_time = time.time()
                        feed_results = uvloop.run(_collect_json())
                        elapsed = time.time() - start_time
                        total_new = sum(r.get("new_articles", 0) for r in feed_results)
                        success_count = sum(
                            1 for r in feed_results if not r.get("error")
                        )
                        error_count = sum(1 for r in feed_results if r.get("error"))
                        serialized_feeds = []
                        for result in feed_results:
                            serialized_feeds.append(
                                {
                                    "feed_name": result.get("feed_name", "?"),
                                    "feed_id": result.get("feed_id", "?"),
                                    "new_articles": result.get("new_articles", 0),
                                    "error": result.get("error"),
                                }
                            )
                        print_json(
                            format_fetch_results(
                                serialized_feeds,
                                total_new,
                                success_count,
                                error_count,
                                elapsed,
                            )
                        )
                    else:
                        # Progress bar mode
                        feed_results: list[dict] = []
                        results_collector = []

                        async def _collect_and_update():
                            """Collect results and update progress."""
                            async for result in fetch_ids_async(ids, concurrency):
                                results_collector.append(result)
                                fp.update(result)
                            return results_collector

                        with FetchProgress(
                            len(ids),
                            f"[cyan]Fetching {len(ids)} feeds by ID (concurrency:{concurrency})...",
                            concurrency,
                        ) as fp:
                            feed_results = uvloop.run(_collect_and_update())

                        elapsed = fp.elapsed_time
                        total_new = fp.total_new
                        success_count = fp.success_count
                        error_count = fp.error_count
                        print_summary(
                            total_new, success_count, error_count, fp.errors, elapsed
                        )
            except Exception as e:
                if json_output:
                    print_json_error(f"Failed to fetch feeds: {e}", "fetch_error")
                    return
                click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
                logger.exception("Failed to fetch feeds")
                sys.exit(1)
            return

        # Case 2: --all flag
        if do_fetch_all:
            try:
                feeds = list_feeds()
                if not feeds:
                    if json_output:
                        print_json(format_fetch_results([], 0, 0, 0, 0.0))
                    else:
                        click.secho(
                            "No feeds subscribed. Use 'feed add <url>' to add one.",
                            fg="yellow",
                        )
                    return

                if json_output:
                    # JSON mode: skip progress bar, collect results directly
                    import time

                    async def _collect_all_json():
                        results = []
                        async for r in fetch_all_async(concurrency=concurrency):
                            results.append(r)
                        return results

                    start_time = time.time()
                    feed_results = uvloop.run(_collect_all_json())
                    elapsed = time.time() - start_time
                    total_new = sum(r.get("new_articles", 0) for r in feed_results)
                    success_count = sum(1 for r in feed_results if not r.get("error"))
                    error_count = sum(1 for r in feed_results if r.get("error"))
                    serialized_feeds = []
                    for result in feed_results:
                        serialized_feeds.append(
                            {
                                "feed_name": result.get("feed_name", "?"),
                                "feed_id": result.get("feed_id", "?"),
                                "new_articles": result.get("new_articles", 0),
                                "error": result.get("error"),
                            }
                        )
                    print_json(
                        format_fetch_results(
                            serialized_feeds,
                            total_new,
                            success_count,
                            error_count,
                            elapsed,
                        )
                    )
                else:
                    # Progress bar mode
                    feed_results: list[dict] = []
                    results_collector = []

                    async def _collect_and_update():
                        """Collect results and update progress."""
                        async for result in fetch_all_async(concurrency=concurrency):
                            results_collector.append(result)
                            fp.update(result)
                        return results_collector

                    with FetchProgress(
                        len(feeds),
                        f"[cyan]Fetching {len(feeds)} feeds (concurrency:{concurrency})...",
                        concurrency,
                    ) as fp:
                        feed_results = uvloop.run(_collect_and_update())

                    elapsed = fp.elapsed_time
                    total_new = fp.total_new
                    success_count = fp.success_count
                    error_count = fp.error_count
                    print_summary(
                        total_new,
                        success_count,
                        error_count,
                        fp.errors,
                        elapsed,
                        prefix="✓ ",
                    )
            except Exception as e:
                if json_output:
                    print_json_error(f"Failed to fetch feeds: {e}", "fetch_error")
                    return
                click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
                logger.exception("Failed to fetch feeds")
                sys.exit(1)
            return

        # Case 3: No arguments
        click.secho("Use --all to fetch all feeds: feedship fetch --all")
        click.secho(
            "Or specify feed IDs to fetch: feedship fetch <feed_id> [<feed_id>...]"
        )

    if profile:
        profiles_dir = Path("profiles")
        profiles_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        profile_file = profiles_dir / f"fetch_{timestamp}.prof"

        profiler = cProfile.Profile()
        profiler.enable()

        try:
            _do_fetch()
        finally:
            profiler.disable()
            profiler.dump_stats(str(profile_file))

            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(20)
            click.echo(f"\n[Profile saved to {profile_file}]")
            click.echo(s.getvalue())
    else:
        _do_fetch()
