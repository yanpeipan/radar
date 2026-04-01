"""Discover RSS/Atom/RDF feeds from a website URL without subscribing."""

# Patch asyncio's executor shutdown timeout to avoid long hangs during cleanup.
# Python 3.13's shutdown_default_executor() waits up to 300 seconds for threads
# to finish, which causes CLI to hang. Reducing to 10 seconds.
import asyncio.constants
import logging
import sys
import time

import click
import uvloop

asyncio.constants.THREAD_JOIN_TIMEOUT = 10

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.text import Text  # noqa: E402

from src.cli.ui import (  # noqa: E402
    DiscoverProgress,
    format_discover_feeds,
    print_json,
    print_json_error,
)
from src.discovery import DiscoveredFeed, discover_feeds  # noqa: E402

logger = logging.getLogger(__name__)


async def _discover_async(url: str, max_depth: int = 1) -> list[DiscoveredFeed]:
    """Async wrapper for discover_feeds.

    Args:
        url: Website URL to discover feeds from.
        max_depth: Maximum crawl depth (1 = current page only, 2+ = BFS crawl).

    Returns:
        List of DiscoveredFeed objects found on the page.
    """
    result = await discover_feeds(url, max_depth)
    return result.feeds


def _display_feeds(feeds: list[DiscoveredFeed], numbered: bool = False) -> None:
    """Display discovered feeds in a Rich table.

    Args:
        feeds: List of DiscoveredFeed objects to display.
        numbered: If True, prepend an index column (#) for selection UI.
    """
    if not feeds:
        click.secho("No feeds discovered.", fg="yellow")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    if numbered:
        table.add_column("#", style="dim", width=4)
    table.add_column("Type", style="dim", width=8)
    table.add_column("Title", max_width=40)
    table.add_column("URL")

    # Color map for feed types
    color_map = {
        "rss": "red",
        "atom": "green",
        "rdf": "blue",
    }

    for i, feed in enumerate(feeds, 1):
        color = color_map.get(feed.feed_type, "white")
        title = feed.title if feed.title else "—"
        type_display = Text(feed.feed_type.upper(), style=color)
        if numbered:
            table.add_row(str(i), type_display, title, feed.url)
        else:
            table.add_row(type_display, title, feed.url)

    console.print(table)


from src.cli import cli  # noqa: E402


@cli.command("discover")
@click.argument("url")
@click.option(
    "--discover-depth",
    default=1,
    type=click.IntRange(1, 10),
    help="Crawl depth for feed discovery (default: 1)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def discover(
    ctx: click.Context, url: str, discover_depth: int, json_output: bool
) -> None:
    """Discover RSS/Atom/RDF feeds from a website URL without subscribing.

    Examples:

      feedship discover example.com
      feedship discover example.com --discover-depth 1
    """
    try:
        start_time = time.time()
        with DiscoverProgress(f"[cyan]Discovering feeds from {url}...") as dp:
            feeds = uvloop.run(_discover_async(url, discover_depth))
            for feed in feeds:
                dp.update(feed)
        elapsed = time.time() - start_time

        if json_output:
            print_json(format_discover_feeds(feeds, elapsed))
            return

        _display_feeds(feeds)
        if feeds:
            click.secho(
                f"Discovered {len(feeds)} feed(s) in {elapsed:.1f}s", fg="green"
            )
    except Exception as e:
        if json_output:
            print_json_error(f"Discovery error: {e}", "discover_error")
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
