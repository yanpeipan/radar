"""CLI interface for RSS reader using click framework.

Provides commands for feed management and article listing.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import click

from src.articles import list_articles, search_articles
from src.crawl import crawl_url
from src.db import init_db
from src.feeds import (
    FeedNotFoundError,
    add_feed,
    list_feeds,
    refresh_feed,
    remove_feed,
)
from src.github import (
    add_github_repo,
    list_github_repos,
    remove_github_repo,
    refresh_github_repo,
    refresh_changelog,
    get_repo_changelog,
    RepoNotFoundError,
    RateLimitError,
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


@cli.command("search")
@click.argument("query")
@click.option("--limit", default=20, help="Maximum number of results")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.pass_context
def article_search(ctx: click.Context, query: str, limit: int, feed_id: Optional[str]) -> None:
    """Search articles by keyword using full-text search.

    Supports FTS5 query syntax:
    - Multiple words default to AND (all must match)
    - Use quotes for exact phrase: "machine learning"
    - Use OR for either: python OR ruby
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        articles = search_articles(query=query, limit=limit, feed_id=feed_id)
        if not articles:
            click.echo("No articles found matching your search.")
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
        click.echo(f"Error: Failed to search articles: {e}", err=True, fg="red")
        logger.exception("Failed to search articles")
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
            click.echo(f"No content extracted from {url}", fg="yellow")
            sys.exit(1)
        title = result.get('title') or 'No title'
        link = result.get('link') or url
        click.echo(f"Crawled: {title} ({link})", fg="green")
        if verbose:
            content_preview = result.get('content', '')[:200] + '...' if result.get('content') else ''
            if content_preview:
                click.echo(f"Content preview: {content_preview}")
    except Exception as e:
        click.echo(f"Error: Failed to crawl {url}: {e}", err=True, fg="red")
        logger.exception("Failed to crawl")
        sys.exit(1)


@cli.group()
@click.pass_context
def repo(ctx: click.Context) -> None:
    """Manage GitHub repositories."""
    pass


@repo.command("add")
@click.argument("url")
@click.pass_context
def repo_add(ctx: click.Context, url: str) -> None:
    """Add a GitHub repository to monitor.

    Examples:

        rss-reader repo add https://github.com/owner/repo

        rss-reader repo add git@github.com:owner/repo.git
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        repo_obj = add_github_repo(url)
        click.echo(f"Added GitHub repo: {repo_obj.name}", fg="green")
        if verbose:
            click.echo(f"Repo ID: {repo_obj.id}")
            if repo_obj.last_tag:
                click.echo(f"Latest release: {repo_obj.last_tag}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to add repo: {e}", err=True, fg="red")
        logger.exception("Failed to add repo")
        sys.exit(1)


@repo.command("list")
@click.pass_context
def repo_list(ctx: click.Context) -> None:
    """List all monitored GitHub repositories."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        repos = list_github_repos()
        if not repos:
            click.echo("No GitHub repos monitored yet. Use 'repo add <url>' to add one.")
            return

        click.echo("ID | Name | Latest Tag")
        click.echo("-" * 60)

        for r in repos:
            tag = r.last_tag or "None"
            if verbose:
                click.echo(f"\n{r.id}")
                click.echo(f"  Name: {r.name}")
                click.echo(f"  Owner: {r.owner}")
                click.echo(f"  Repo: {r.repo}")
                click.echo(f"  Latest Tag: {tag}")
                click.echo(f"  Last Fetched: {r.last_fetched or 'Never'}")
            else:
                click.echo(f"{r.id[:8]}... | {r.name[:40]} | {tag}")
    except Exception as e:
        click.echo(f"Error: Failed to list repos: {e}", err=True, fg="red")
        logger.exception("Failed to list repos")
        sys.exit(1)


@repo.command("remove")
@click.argument("repo_id")
@click.pass_context
def repo_remove(ctx: click.Context, repo_id: str) -> None:
    """Remove a GitHub repository by ID."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        removed = remove_github_repo(repo_id)
        if removed:
            click.echo(f"Removed repo: {repo_id}", fg="green")
        else:
            click.echo(f"Repo not found: {repo_id}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to remove repo: {e}", err=True, fg="red")
        logger.exception("Failed to remove repo")
        sys.exit(1)


@repo.command("refresh")
@click.argument("repo_id", required=False)
@click.pass_context
def repo_refresh(ctx: click.Context, repo_id: Optional[str]) -> None:
    """Refresh GitHub repo(s) to fetch latest releases.

    If repo_id is provided, refreshes that specific repo.
    Otherwise, refreshes all monitored GitHub repos.
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        if repo_id:
            # Refresh single repo
            result = refresh_github_repo(repo_id)
            if result.get("new_release"):
                release = result["release"]
                click.echo(f"New release: {release.tag_name}", fg="green")
                if verbose and release.name:
                    click.echo(f"Title: {release.name}")
            elif result.get("error"):
                click.echo(f"Error: {result['error']}", fg="red")
                if "rate limit" in result["error"].lower():
                    click.echo("Hint: Set GITHUB_TOKEN environment variable for 5000 req/hour", fg="yellow")
                sys.exit(1)
            else:
                click.echo(result.get("message", "No new release"), fg="yellow")
        else:
            # Refresh all repos
            repos = list_github_repos()
            if not repos:
                click.echo("No GitHub repos monitored. Use 'repo add <url>' first.")
                return

            new_release_count = 0
            for r in repos:
                try:
                    result = refresh_github_repo(r.id)
                    if result.get("new_release"):
                        new_release_count += 1
                        click.echo(f"New release for {r.name}: {result['release'].tag_name}", fg="green")
                    elif result.get("error"):
                        click.echo(f"Error refreshing {r.name}: {result['error']}", fg="yellow")
                except Exception as e:
                    click.echo(f"Error refreshing {r.name}: {e}", fg="yellow")

            if new_release_count > 0:
                click.echo(f"\nFetched {new_release_count} new release(s)", fg="green")
            else:
                click.echo("No new releases found")

    except RepoNotFoundError:
        click.echo(f"Repo not found: {repo_id}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to refresh repos: {e}", err=True, fg="red")
        logger.exception("Failed to refresh repos")
        sys.exit(1)


@repo.command("changelog")
@click.argument("repo_id", required=False)
@click.option("--refresh", is_flag=True, help="Refresh changelog before displaying")
@click.pass_context
def repo_changelog(ctx: click.Context, repo_id: Optional[str], refresh: bool) -> None:
    """View or refresh changelog for a GitHub repository.

    If repo_id is provided, shows changelog for that specific repo.
    Without repo_id, prompts to select from available repos.

    Use --refresh to fetch the latest changelog before displaying.
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False

    try:
        if repo_id:
            # Single repo specified
            _show_repo_changelog(repo_id, refresh, verbose)
        else:
            # List all repos and let user select one
            repos = list_github_repos()
            if not repos:
                click.echo("No GitHub repos monitored. Use 'repo add <url>' first.")
                return

            click.echo("Select a repo to view changelog:")
            for i, r in enumerate(repos, 1):
                click.echo(f"  {i}. {r.name}")
            click.echo()

            # For now, show changelog for first repo with stored changelog
            for r in repos:
                changelog = get_repo_changelog(r.id)
                if changelog:
                    _display_changelog(r, changelog, verbose)
                    return

            click.echo("No changelogs stored yet. Use 'repo changelog <id> --refresh' to fetch.")

    except RepoNotFoundError:
        click.echo(f"Repo not found: {repo_id}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True, fg="red")
        logger.exception("Failed to get changelog")
        sys.exit(1)


def _show_repo_changelog(repo_id: str, refresh: bool, verbose: bool) -> None:
    """Helper to show changelog for a specific repo.

    Args:
        repo_id: ID of the repo to show changelog for.
        refresh: Whether to refresh before showing.
        verbose: Whether to show verbose output.
    """
    repo = None
    # Find repo name
    repos = list_github_repos()
    for r in repos:
        if r.id == repo_id:
            repo = r
            break

    if not repo:
        click.echo(f"Repo not found: {repo_id}", fg="red")
        sys.exit(1)

    if refresh:
        # Refresh changelog first
        result = refresh_changelog(repo_id)
        if result.get("error"):
            click.echo(f"Error refreshing changelog: {result['error']}", fg="red")
            # Fall through to show stored changelog if available
        elif result.get("changelog_found"):
            click.echo(f"Changelog refreshed: {result.get('filename', 'unknown')}", fg="green")
        else:
            click.echo(f"No changelog found: {result.get('message', 'unknown')}", fg="yellow")
            return

    # Get stored changelog
    changelog = get_repo_changelog(repo_id)
    if changelog:
        _display_changelog(repo, changelog, verbose)
    else:
        click.echo(f"No changelog stored for {repo.name}. Use --refresh to fetch.", fg="yellow")


def _display_changelog(repo, changelog: dict, verbose: bool) -> None:
    """Display a changelog article.

    Args:
        repo: GitHubRepo object.
        changelog: Dict with title, link, content, created_at.
        verbose: Whether to show full content or just header.
    """
    click.echo(f"\n=== {changelog['title']} ===")
    click.echo(f"Source: {changelog['link']}")
    click.echo(f"Stored: {changelog['created_at']}")
    click.echo()

    if verbose:
        # Show full content
        click.echo(changelog['content'])
    else:
        # Show first 2000 characters
        content = changelog['content']
        if len(content) > 2000:
            click.echo(content[:2000])
            click.echo(f"\n... (truncated, use --verbose for full content)")
        else:
            click.echo(content)


if __name__ == "__main__":
    cli()
