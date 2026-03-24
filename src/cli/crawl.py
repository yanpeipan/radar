"""Crawl command for RSS reader CLI."""

import sys
import logging

import click

from src.crawl import crawl_url

logger = logging.getLogger(__name__)


# Import cli from parent package
from src.cli import cli


@cli.command("crawl")
@click.argument("url")
@click.option("--ignore-robots", is_flag=True, help="Ignore robots.txt and crawl anyway (lazy mode disabled)")
@click.pass_context
def crawl(ctx: click.Context, url: str, ignore_robots: bool) -> None:
    """Fetch and store content from a URL as an article.

    Uses Readability algorithm to extract article content from webpages.
    Respects robots.txt by default (use --ignore-robots to override).

    Examples:

        rss-reader crawl https://example.com/article

        rss-reader crawl https://example.com --ignore-robots
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        result = crawl_url(url, ignore_robots=ignore_robots)
        if result is None:
            click.secho(f"No content extracted from {url}", fg="yellow")
            sys.exit(1)
        title = result.get('title') or 'No title'
        link = result.get('link') or url
        click.secho(f"Crawled: {title} ({link})", fg="green")
        if verbose:
            content_preview = result.get('content', '')[:200] + '...' if result.get('content') else ''
            if content_preview:
                click.secho(f"Content preview: {content_preview}")
    except Exception as e:
        click.secho(f"Error: Failed to crawl {url}: {e}", err=True, fg="red")
        logger.exception("Failed to crawl")
        sys.exit(1)
