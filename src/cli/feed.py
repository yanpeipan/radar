"""Feed management commands for RSS reader CLI."""

import sys
import logging
from typing import Optional

import click
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.application.feed import (
    FeedNotFoundError,
    add_feed,
    list_feeds,
    remove_feed,
    fetch_one,
    fetch_all,
)

logger = logging.getLogger(__name__)


def _get_provider_type(url: str) -> str:
    """Determine provider type from URL pattern.

    Args:
        url: The feed URL.

    Returns:
        "GitHub" if URL contains github.com, "RSS" otherwise.
    """
    if "github.com" in url.lower():
        return "GitHub"
    return "RSS"


# Import cli from parent package
from src.cli import cli


@cli.group()
@click.pass_context
def feed(ctx: click.Context) -> None:
    """Manage RSS/Atom feeds."""
    pass


@feed.command("add")
@click.argument("url")
@click.pass_context
def feed_add(ctx: click.Context, url: str) -> None:
    """Add a new feed by URL (auto-detects provider type)."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
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


@feed.command("refresh")
@click.argument("feed_id")
@click.pass_context
def feed_refresh(ctx: click.Context, feed_id: str) -> None:
    """Refresh a single feed to fetch new articles."""
    try:
        result = fetch_one(feed_id)
        if "error" in result:
            click.secho(f"Error refreshing feed: {result['error']}", fg="red")
            sys.exit(1)
        new_count = result.get("new_articles", 0)
        if new_count > 0:
            click.secho(f"Fetched {new_count} new articles", fg="green")
        else:
            click.secho("No new articles available", fg="yellow")
    except FeedNotFoundError:
        click.secho(f"Feed not found: {feed_id}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to refresh feed: {e}", err=True, fg="red")
        logger.exception("Failed to refresh feed")
        sys.exit(1)


@cli.command("fetch")
@click.option("--all", "do_fetch_all", is_flag=True, help="Fetch all feeds")
@click.argument("urls", nargs=-1, required=False)
@click.pass_context
def fetch(ctx: click.Context, do_fetch_all: bool, urls: tuple) -> None:
    """Fetch new articles from feeds or crawl specific URLs.

    Examples:

      rss-reader fetch --all              Fetch all subscribed feeds

      rss-reader fetch https://example.com  Crawl a single URL

      rss-reader fetch https://ex.com https://py.com  Crawl multiple URLs
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False

    # Case 1: URL arguments provided
    if urls:
        from src.application.crawl import crawl_url
        from src.storage.sqlite import store_article

        success_count = 0
        fail_count = 0
        for url in urls:
            try:
                result = crawl_url(url)
                if result:
                    title = result.get("title", "Untitled")
                    click.secho(f"Fetched: {title} ({url})", fg="green")
                    success_count += 1
                else:
                    click.secho(f"Failed to fetch {url}: No content", fg="red")
                    fail_count += 1
            except Exception as e:
                click.secho(f"Failed to fetch {url}: {e}", fg="red")
                fail_count += 1

        if fail_count > 0:
            click.secho(f"Completed: {success_count} succeeded, {fail_count} failed", fg="yellow")
            sys.exit(1)
        else:
            click.secho(f"Completed: {success_count} URL(s) fetched", fg="green")
        return

    # Case 2: --all flag
    if do_fetch_all:
        try:
            from src.application.feed import fetch_one, list_feeds

            feeds = list_feeds()
            if not feeds:
                click.secho("No feeds subscribed. Use 'feed add <url>' to add one.", fg="yellow")
                return

            total_new = 0
            success_count = 0
            error_count = 0
            errors = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task(f"[cyan]Fetching {len(feeds)} feeds...", total=len(feeds))

                for feed_obj in feeds:
                    progress.update(task, description=f"[cyan]Fetching {feed_obj.name}...")
                    try:
                        result = fetch_one(feed_obj)
                        new_articles = result.get("new_articles", 0)
                        if new_articles > 0:
                            click.secho(f"  ✓ {feed_obj.name}: +{new_articles} articles", fg="green")
                        else:
                            click.secho(f"  ✓ {feed_obj.name}: up to date", fg="blue")
                        total_new += new_articles
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(f"{feed_obj.name}: {e}")
                        click.secho(f"  ✗ {feed_obj.name}: {e}", fg="red")
                    progress.advance(task)

            # Summary
            click.secho("")
            if error_count == 0:
                click.secho(
                    f"✓ Fetched {total_new} articles from {success_count} feeds",
                    fg="green",
                )
            else:
                click.secho(
                    f"✓ Fetched {total_new} articles from {success_count} feeds, {error_count} errors",
                    fg="yellow",
                )

        except Exception as e:
            click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
            logger.exception("Failed to fetch feeds")
            sys.exit(1)
        return

    # Case 3: No arguments
    click.secho("Use --all to fetch all feeds: rss-reader fetch --all")
    click.secho("Or specify URLs to crawl: rss-reader fetch <url> [url ...]")
