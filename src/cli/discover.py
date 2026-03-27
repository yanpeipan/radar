"""Discover RSS/Atom/RDF feeds from a website URL without subscribing."""

import sys
import logging

import click
import uvloop
from rich.console import Console
from rich.table import Table

from src.discovery import discover_feeds, DiscoveredFeed

logger = logging.getLogger(__name__)


async def _discover_async(url: str) -> list[DiscoveredFeed]:
    """Async wrapper for discover_feeds.

    Args:
        url: Website URL to discover feeds from.

    Returns:
        List of DiscoveredFeed objects found on the page.
    """
    return await discover_feeds(url)


def _display_feeds(feeds: list[DiscoveredFeed]) -> None:
    """Display discovered feeds in a Rich table.

    Args:
        feeds: List of DiscoveredFeed objects to display.
    """
    if not feeds:
        click.secho("No feeds discovered.", fg="yellow")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="dim", width=8)
    table.add_column("Title", max_width=40)
    table.add_column("URL")

    # Color map for feed types
    color_map = {
        "rss": "red",
        "atom": "green",
        "rdf": "blue",
    }

    for feed in feeds:
        color = color_map.get(feed.feed_type, "white")
        title = feed.title if feed.title else "—"
        type_display = click.style(feed.feed_type.upper(), fg=color)
        table.add_row(type_display, title, feed.url)

    console.print(table)
    click.secho(f"Discovered {len(feeds)} feed(s)", fg="green")


from src.cli import cli


@cli.command("discover")
@click.argument("url")
@click.option(
    "--discover-deep",
    default=1,
    type=click.IntRange(1, 10),
    help="Crawl depth for feed discovery (default: 1)",
)
@click.pass_context
def discover(ctx: click.Context, url: str, discover_depth: int) -> None:
    """Discover RSS/Atom/RDF feeds from a website URL without subscribing.

    Examples:

      rss-reader discover example.com
      rss-reader discover example.com --discover-deep 1
    """
    if discover_depth > 1:
        click.secho(
            "Deep crawling (depth > 1) is not yet implemented. "
            "Use depth=1 for single-page discovery.",
            fg="yellow",
        )
        return

    try:
        feeds = uvloop.run(_discover_async(url))
        _display_feeds(feeds)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
