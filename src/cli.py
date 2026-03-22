"""CLI interface for RSS reader using click framework.

Provides commands for feed management and article listing.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import click

from src.articles import list_articles
from src.db import init_db
from src.feeds import (
    FeedNotFoundError,
    add_feed,
    list_feeds,
    refresh_feed,
    remove_feed,
)

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """RSS reader CLI - manage feeds and read articles."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Initialize database on every command
    init_db()


@cli.group()
@click.pass_context
def feed(ctx: click.Context) -> None:
    """Manage RSS/Atom feeds."""
    pass


@feed.command("add")
@click.argument("url")
@click.pass_context
def feed_add(ctx: click.Context, url: str) -> None:
    """Add a new feed by URL."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        feed_obj = add_feed(url)
        click.echo(f"Added feed: {feed_obj.name} ({feed_obj.url})", fg="green")
        if verbose:
            click.echo(f"Feed ID: {feed_obj.id}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to add feed: {e}", err=True, fg="red")
        logger.exception("Failed to add feed")
        sys.exit(1)


@feed.command("list")
@click.pass_context
def feed_list(ctx: click.Context) -> None:
    """List all subscribed feeds."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        feeds = list_feeds()
        if not feeds:
            click.echo("No feeds subscribed yet. Use 'feed add <url>' to add one.")
            return

        # Print table header
        click.echo("ID  | Name | URL | Articles | Last Fetched")
        click.echo("-" * 80)

        for f in feeds:
            last_fetched = f.last_fetched or "Never"
            if verbose:
                click.echo(
                    f"{f.id}\n"
                    f"  Name: {f.name}\n"
                    f"  URL: {f.url}\n"
                    f"  Articles: {getattr(f, 'articles_count', 0)}\n"
                    f"  Last Fetched: {last_fetched}"
                )
            else:
                click.echo(
                    f"{f.id[:8]}... | {f.name[:30]} | {f.url[:40]} | "
                    f"{getattr(f, 'articles_count', 0)} | {last_fetched[:10]}"
                )
    except Exception as e:
        click.echo(f"Error: Failed to list feeds: {e}", err=True, fg="red")
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
            click.echo(f"Removed feed: {feed_id}", fg="green")
        else:
            click.echo(f"Feed not found: {feed_id}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to remove feed: {e}", err=True, fg="red")
        logger.exception("Failed to remove feed")
        sys.exit(1)


@feed.command("refresh")
@click.argument("feed_id")
@click.pass_context
def feed_refresh(ctx: click.Context, feed_id: str) -> None:
    """Refresh a single feed to fetch new articles."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        result = refresh_feed(feed_id)
        if "error" in result:
            click.echo(f"Error refreshing feed: {result['error']}", fg="red")
            sys.exit(1)
        new_count = result.get("new_articles", 0)
        if new_count > 0:
            click.echo(f"Fetched {new_count} new articles", fg="green")
        else:
            click.echo("No new articles available", fg="yellow")
    except FeedNotFoundError:
        click.echo(f"Feed not found: {feed_id}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to refresh feed: {e}", err=True, fg="red")
        logger.exception("Failed to refresh feed")
        sys.exit(1)


@cli.command("article")
@click.option("--limit", default=20, help="Maximum number of articles to show")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.pass_context
def article_list(ctx: click.Context, limit: int, feed_id: Optional[str]) -> None:
    """List recent articles from all feeds or a specific feed."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        articles = list_articles(limit=limit, feed_id=feed_id)
        if not articles:
            click.echo("No articles found. Add some feeds and fetch them first.")
            return

        click.echo("Title | Feed | Date")
        click.echo("-" * 80)

        for article in articles:
            title = article.title or "No title"
            feed_name = article.feed_name or "Unknown"
            pub_date = article.pub_date or "No date"

            if verbose:
                click.echo(f"\nTitle: {title}")
                click.echo(f"Feed: {feed_name}")
                click.echo(f"Date: {pub_date}")
                if article.link:
                    click.echo(f"Link: {article.link}")
                if article.description:
                    desc_preview = article.description[:100] + "..." if len(article.description) > 100 else article.description
                    click.echo(f"Description: {desc_preview}")
            else:
                click.echo(f"{title[:50]} | {feed_name[:20]} | {pub_date[:10]}")
    except Exception as e:
        click.echo(f"Error: Failed to list articles: {e}", err=True, fg="red")
        logger.exception("Failed to list articles")
        sys.exit(1)


@cli.command("fetch")
@click.option("--all", "fetch_all", is_flag=True, help="Fetch all feeds")
@click.pass_context
def fetch(ctx: click.Context, fetch_all: bool) -> None:
    """Fetch new articles from feeds."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False

    if not fetch_all:
        click.echo("Use --all to fetch all feeds: feed fetch --all")
        click.echo("Or use 'feed refresh <id>' to refresh a specific feed")
        return

    try:
        feeds = list_feeds()
        if not feeds:
            click.echo("No feeds subscribed. Use 'feed add <url>' to add one.", fg="yellow")
            return

        total_new = 0
        success_count = 0
        error_count = 0
        errors: list[str] = []

        for feed_obj in feeds:
            try:
                result = refresh_feed(feed_obj.id)
                new_articles = result.get("new_articles", 0)
                total_new += new_articles
                success_count += 1
                if verbose:
                    click.echo(f"Fetched {new_articles} articles from {feed_obj.name}")
            except Exception as e:
                error_count += 1
                errors.append(f"{feed_obj.name}: {e}")
                # Per-feed error isolation: continue with next feed
                click.echo(f"Warning: Failed to fetch {feed_obj.name}: {e}", fg="yellow")

        # Summary
        if error_count == 0:
            click.echo(
                f"Fetched {total_new} articles from {success_count} feeds",
                fg="green",
            )
        else:
            click.echo(
                f"Fetched {total_new} articles from {success_count} feeds, {error_count} errors",
                fg="yellow",
            )
            if verbose and errors:
                for err in errors:
                    click.echo(f"  - {err}", fg="red")

    except Exception as e:
        click.echo(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
        logger.exception("Failed to fetch feeds")
        sys.exit(1)


if __name__ == "__main__":
    cli()
