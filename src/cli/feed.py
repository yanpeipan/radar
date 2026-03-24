"""Feed management commands for RSS reader CLI."""

import sys
import logging
from typing import Optional

import click

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
@click.option("--all", "fetch_all", is_flag=True, help="Fetch all feeds")
@click.pass_context
def fetch(ctx: click.Context, fetch_all: bool) -> None:
    """Fetch new articles from feeds."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False

    if not fetch_all:
        click.secho("Use --all to fetch all feeds: feed fetch --all")
        click.secho("Or use 'feed refresh <id>' to refresh a specific feed")
        return

    try:
        result = fetch_all()
        total_new = result["total_new"]
        success_count = result["success_count"]
        error_count = result["error_count"]
        errors = result["errors"]

        if error_count == 0:
            click.secho(
                f"Fetched {total_new} articles from {success_count} feeds",
                fg="green",
            )
        else:
            click.secho(
                f"Fetched {total_new} articles from {success_count} feeds. {error_count} errors",
                fg="yellow",
            )
            if verbose and errors:
                for err in errors:
                    click.secho(f"  - {err}", fg="red")

    except Exception as e:
        click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
        logger.exception("Failed to fetch feeds")
        sys.exit(1)
