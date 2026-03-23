"""CLI interface for RSS reader using click framework.

Provides commands for feed management and article listing.
"""

from __future__ import annotations

import importlib
import logging
import platform
import subprocess
import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.articles import get_article_detail, list_articles, search_articles
from src.crawl import crawl_url
from src.db import (
    add_tag,
    get_article_tags,
    get_release_tags,
    get_tag_article_counts,
    init_db,
    list_tags,
    remove_tag,
    tag_article,
    tag_github_release,
)
from src.tag_rules import add_rule, remove_rule, list_rules, edit_rule
from src.tag_rules import apply_rules_to_article
from src.providers import discover_or_default

# Import run_auto_tagging from src/tags.py module (not the src/tags/ package)
# This uses importlib.machinery to explicitly load the module by file path
# to avoid the naming conflict where src/tags/ package shadows src/tags.py module
import importlib.machinery
import pathlib
_tags_module_path = pathlib.Path(__file__).parent / "tags.py"
_loader = importlib.machinery.SourceFileLoader("src_tags_module", str(_tags_module_path))
_spec = importlib.util.spec_from_loader("src_tags_module", _loader)
_tags_module = importlib.util.module_from_spec(_spec)
_loader.exec_module(_tags_module)
run_auto_tagging = _tags_module.run_auto_tagging
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
        click.secho(f"Added feed: {feed_obj.name} ({feed_obj.url})", fg="green")
        if verbose:
            click.secho(f"Feed ID: {feed_obj.id}")
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
    """List all subscribed feeds."""
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        feeds = list_feeds()
        if not feeds:
            click.secho("No feeds subscribed yet. Use 'feed add <url>' to add one.")
            return

        # Print table header
        click.secho("ID  | Name | URL | Articles | Last Fetched")
        click.secho("-" * 80)

        for f in feeds:
            last_fetched = f.last_fetched or "Never"
            if verbose:
                click.secho(
                    f"{f.id}\n"
                    f"  Name: {f.name}\n"
                    f"  URL: {f.url}\n"
                    f"  Articles: {getattr(f, 'articles_count', 0)}\n"
                    f"  Last Fetched: {last_fetched}"
                )
            else:
                click.secho(
                    f"{f.id} | {f.name[:30]} | {f.url[:40]} | "
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
    verbose = ctx.parent and ctx.parent.obj.get("verbose")
    try:
        result = refresh_feed(feed_id)
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


@cli.group()
@click.pass_context
def article(ctx: click.Context) -> None:
    """Manage articles."""
    pass


@article.command("list")
@click.option("--limit", default=20, help="Maximum number of articles to show")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.option("--tag", default=None, help="Filter by tag name")
@click.option("--tags", default=None, help="Filter by multiple tags (comma-separated, OR logic)")
@click.option("--verbose", is_flag=True, help="Show full article IDs (32 chars)")
@click.pass_context
def article_list(ctx: click.Context, limit: int, feed_id: Optional[str], tag: Optional[str], tags: Optional[str], verbose: bool) -> None:
    """List recent articles from all feeds or a specific feed.

    Use --tag to filter by a single tag.
    Use --tags a,b for multiple tags (OR logic - shows articles with ANY of the tags).
    Use --verbose to show full 32-char article IDs instead of truncated 8-char IDs.
    """
    verbose = verbose or (ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False)
    try:
        from src.articles import list_articles_with_tags, get_articles_with_tags
        articles = list_articles_with_tags(limit=limit, feed_id=feed_id, tag=tag, tags=tags)
        if not articles:
            click.secho("No articles found. Add some feeds and fetch them first.")
            return

        # Separate article IDs and release IDs
        article_ids = [a.id for a in articles if a.source_type == "feed"]
        release_ids = [a.id for a in articles if a.source_type == "github"]

        # Batch fetch tags for all items (articles and releases)
        tags_map = get_articles_with_tags(article_ids, release_ids if release_ids else None)

        # Create rich table
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=8 if not verbose else 36)
        table.add_column("Tags", max_width=12, overflow="ellipsis")
        table.add_column("Title")
        table.add_column("Source", max_width=20)
        table.add_column("Date", max_width=10)

        for article in articles:
            title = article.title or "No title"
            pub_date = article.pub_date or "No date"

            # Show GitHub source or feed source
            if article.source_type == "github":
                source = f"{article.repo_name}@{article.release_tag}" if article.release_tag else article.repo_name
            else:
                source = article.feed_name or "Unknown"

            # Get tags from batch-fetched map
            article_tags = tags_map.get(article.id, [])
            tags_str = ",".join(article_tags) if article_tags else "-"

            # Use full ID if verbose, otherwise truncate to 8 chars
            id_display = article.id if verbose else article.id[:8]

            table.add_row(id_display, tags_str, title[:50], source[:20], pub_date[:10])

        console.print(table)
    except Exception as e:
        click.secho(f"Error: Failed to list articles: {e}", err=True, fg="red")
        logger.exception("Failed to list articles")
        sys.exit(1)


@article.command("view")
@click.argument("article_id")
@click.option("--verbose", is_flag=True, help="Show full content without truncation")
@click.pass_context
def article_view(ctx: click.Context, article_id: str, verbose: bool) -> None:
    """View full article details including content.

    Shows title, source/feed, date, tags, link, and full content.
    Works for both feed articles and GitHub releases.
    Content is truncated to 2000 characters unless --verbose is specified.
    """
    try:
        from src.db import get_release_detail

        # First try article
        article = get_article_detail(article_id)

        # If not found, try release
        if not article:
            release = get_release_detail(article_id)
            if release:
                # Format release as article-like dict for display
                article = {
                    "id": release["id"],
                    "feed_name": release["repo_name"],
                    "pub_date": release["published_at"],
                    "tags": release["tags"],
                    "link": release["html_url"],
                    "title": release["name"] or release["tag_name"],
                    "content": release["body"],
                    "source_type": "github",
                }
            else:
                click.secho(f"Article not found: {article_id}", fg="red")
                sys.exit(1)

        console = Console()

        # Create metadata table
        meta_table = Table(show_header=False, box=None)
        source_type = article.get("source_type", "feed")
        meta_table.add_row("Source:", article["feed_name"] or "Unknown")
        meta_table.add_row("Type:", source_type.capitalize())
        meta_table.add_row("Date:", article["pub_date"] or "No date")

        # Tags
        tags_str = ", ".join(article["tags"]) if article["tags"] else "-"
        meta_table.add_row("Tags:", tags_str)

        # Link
        link = article["link"] or "No link"
        meta_table.add_row("Link:", link)

        # Display panel with title
        title = article["title"] or "No title"
        subtitle = f"{article['feed_name']} | {article['pub_date'] or 'No date'}"
        panel = Panel(meta_table, title=title, subtitle=subtitle)
        console.print(panel)

        # Display content
        if article["content"]:
            content = article["content"] if verbose else article["content"][:2000]
            if not verbose and len(article["content"]) > 2000:
                content += "\n\n... (truncated, use --verbose for full content)"
            console.print()
            console.print(content)
        else:
            console.print("\n[yellow]No content available[/yellow]")

    except Exception as e:
        click.secho(f"Error: Failed to view article: {e}", err=True, fg="red")
        logger.exception("Failed to view article")
        sys.exit(1)


def open_in_browser(url: str) -> None:
    """Open a URL in the default browser.

    Args:
        url: The URL to open.

    Raises:
        RuntimeError: If the platform is not supported.
    """
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", url])
    elif system == "Linux":
        subprocess.run(["xdg-open", url])
    elif system == "Windows":
        subprocess.run(["start", "", url], shell=True)
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


@article.command("open")
@click.argument("article_id")
@click.pass_context
def article_open(ctx: click.Context, article_id: str) -> None:
    """Open article URL in default browser. Works for both articles and releases."""
    try:
        from src.db import get_release_detail

        article = get_article_detail(article_id)

        # If not found, try release
        if not article:
            release = get_release_detail(article_id)
            if release:
                link = release["html_url"]
                source_type = "release"
            else:
                click.secho(f"Article not found: {article_id}", fg="red")
                sys.exit(1)
        else:
            link = article.get("link")
            source_type = "article"

        if not link:
            click.secho(f"No link available for this {source_type}", fg="red")
            sys.exit(1)

        open_in_browser(link)
        click.secho(f"Opened {link} in browser", fg="green")

    except RuntimeError as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to open article: {e}", err=True, fg="red")
        logger.exception("Failed to open article")
        sys.exit(1)


@article.command("tag")
@click.argument("article_id", required=False)
@click.argument("tag_name", required=False)
@click.option("--auto", "auto_tag", is_flag=True, help="Run AI clustering to auto-tag articles")
@click.option("--rules", "apply_rules", is_flag=True, help="Apply keyword/regex rules to untagged articles")
@click.option("--eps", default=0.3, help="DBSCAN eps parameter for clustering")
@click.option("--min-samples", default=3, help="DBSCAN min_samples parameter")
@click.pass_context
def article_tag(ctx: click.Context, article_id: Optional[str], tag_name: Optional[str], auto_tag: bool, apply_rules: bool, eps: float, min_samples: int) -> None:
    """Tag an article manually or run auto-tagging.

    Manual: article tag <article-id> <tag-name>
    Auto: article tag --auto [--eps 0.3 --min-samples 3]
    Rules: article tag --rules
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False

    if auto_tag:
        # Run AI clustering (D-10, D-11, D-12, D-13)
        try:
            click.secho("Running AI clustering for auto-tagging...", fg="cyan")
            tag_map = run_auto_tagging(eps=eps, min_samples=min_samples)
            if tag_map:
                click.secho(f"Created {len(tag_map)} tag(s) from clustering:", fg="green")
                for tag_name, article_ids in tag_map.items():
                    click.secho(f"  [{tag_name}] - {len(article_ids)} articles")
            else:
                click.secho("No clusters found. Try with more articles.", fg="yellow")
        except Exception as e:
            click.secho(f"Error in clustering: {e}", err=True, fg="red")
            logger.exception("Auto-tagging failed")
            sys.exit(1)

    elif apply_rules:
        # Apply keyword/regex rules to all untagged articles
        try:
            from src.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.title, a.description FROM articles a
                LEFT JOIN article_tags at ON a.id = at.article_id
                WHERE at.article_id IS NULL
            """)
            untagged = cursor.fetchall()
            conn.close()

            if not untagged:
                click.secho("No untagged articles found.", fg="yellow")
                return

            click.secho(f"Applying rules to {len(untagged)} untagged articles...", fg="cyan")
            applied_count = 0
            for row in untagged:
                matched = apply_rules_to_article(row["id"], row["title"], row["description"])
                if matched:
                    applied_count += 1
                    if verbose:
                        click.secho(f"  {row['title'][:40]} -> {', '.join(matched)}")

            click.secho(f"Applied rules to {applied_count} article(s)", fg="green")
        except Exception as e:
            click.secho(f"Error applying rules: {e}", err=True, fg="red")
            sys.exit(1)

    elif article_id and tag_name:
        # Manual tagging - auto-detect if article_id is a release or article
        try:
            from src.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Check if it's a GitHub release ID
            cursor.execute("SELECT id FROM github_releases WHERE id = ? OR id LIKE ? || '%'", (article_id, article_id))
            release_row = cursor.fetchone()

            if release_row:
                # It's a GitHub release
                tagged = tag_github_release(release_row["id"], tag_name)
                if tagged:
                    click.secho(f"Tagged release {article_id} with '{tag_name}'", fg="green")
                else:
                    click.secho(f"Failed to tag release", fg="red")
                    sys.exit(1)
            else:
                # It's a feed article
                tagged = tag_article(article_id, tag_name)
                if tagged:
                    click.secho(f"Tagged article {article_id} with '{tag_name}'", fg="green")
                else:
                    click.secho(f"Failed to tag article", fg="red")
                    sys.exit(1)
            conn.close()
        except Exception as e:
            click.secho(f"Error: {e}", err=True, fg="red")
            sys.exit(1)

    else:
        click.secho("Usage: article tag <article-id> <tag-name>", fg="yellow")
        click.secho("   or: article tag --auto [--eps 0.3 --min-samples 3]")
        click.secho("   or: article tag --rules")
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
            click.secho("No articles found matching your search.")
            return

        click.secho("Title | Source | Date")
        click.secho("-" * 80)

        for article in articles:
            title = article.title or "No title"
            pub_date = article.pub_date or "No date"

            # Show GitHub source or feed source
            if article.source_type == "github":
                source = f"{article.repo_name}@{article.release_tag}" if article.release_tag else article.repo_name
            else:
                source = article.feed_name or "Unknown"

            if verbose:
                click.secho(f"\nTitle: {title}")
                click.secho(f"Source: {source}")
                click.secho(f"Date: {pub_date}")
                if article.link:
                    click.secho(f"Link: {article.link}")
                if article.description:
                    desc_preview = article.description[:100] + "..." if len(article.description) > 100 else article.description
                    click.secho(f"Description: {desc_preview}")
            else:
                click.secho(f"{title[:50]} | {source[:25]} | {pub_date[:10]}")
    except Exception as e:
        click.secho(f"Error: Failed to search articles: {e}", err=True, fg="red")
        logger.exception("Failed to search articles")
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
        feeds = list_feeds()
        if not feeds:
            click.secho("No feeds subscribed. Use 'feed add <url>' to add one.", fg="yellow")
            return

        total_new = 0
        success_count = 0
        error_count = 0
        errors: list[str] = []

        for feed_obj in feeds:
            try:
                # Use discover_or_default to find provider for this feed URL
                providers = discover_or_default(feed_obj.url)
                if not providers:
                    click.secho(f"Warning: No provider for {feed_obj.name}", fg="yellow")
                    continue

                provider = providers[0]  # highest priority match
                provider_name = provider.__class__.__name__.replace("Provider", "")

                # Crawl using the discovered provider
                raw_items = provider.crawl(feed_obj.url)
                if not raw_items:
                    if verbose:
                        click.secho(f"No items from {feed_obj.name} via {provider_name}")
                    continue

                # Parse and store each item
                for raw in raw_items:
                    article = provider.parse(raw)
                    # Store article (reuse existing pattern from refresh_feed)
                    new_article = _store_article_from_provider(
                        feed_id=feed_obj.id,
                        article=article,
                        provider_name=provider_name,
                    )
                    if new_article:
                        total_new += 1

                success_count += 1
                if verbose:
                    click.secho(f"Fetched {len(raw_items)} items from {feed_obj.name} via {provider_name}")

            except Exception as e:
                error_count += 1
                errors.append(f"{feed_obj.name}: {e}")
                click.secho(f"Warning: Failed to fetch {feed_obj.name}: {e}", fg="yellow")

        # Summary
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


def _store_article_from_provider(feed_id: str, article: dict, provider_name: str) -> bool:
    """Store an article from provider parse() result.

    Args:
        feed_id: The feed ID to associate with.
        article: Article dict from provider.parse().
        provider_name: Name of provider for logging.

    Returns:
        True if new article was stored, False if duplicate or error.
    """
    from src.db import get_connection
    from src.feeds import generate_article_id
    from datetime import datetime, timezone

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Generate article ID if not provided
        article_id = article.get("guid") or generate_article_id(article)

        now = datetime.now(timezone.utc).isoformat()

        cursor.execute(
            """
            INSERT OR IGNORE INTO articles (id, feed_id, title, link, guid, pub_date, description, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                feed_id,
                article.get("title"),
                article.get("link"),
                article.get("guid") or article_id,
                article.get("pub_date"),
                article.get("description"),
                article.get("content"),
                now,
            ),
        )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        logger.warning(f"Failed to store article from {provider_name}: {e}")
        return False


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
        click.secho(f"Added GitHub repo: {repo_obj.name}", fg="green")
        if verbose:
            click.secho(f"Repo ID: {repo_obj.id}")
            if repo_obj.last_tag:
                click.secho(f"Latest release: {repo_obj.last_tag}")
    except ValueError as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to add repo: {e}", err=True, fg="red")
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
            click.secho("No GitHub repos monitored yet. Use 'repo add <url>' to add one.")
            return

        click.secho("ID | Name | Latest Tag")
        click.secho("-" * 60)

        for r in repos:
            tag = r.last_tag or "None"
            if verbose:
                click.secho(f"\n{r.id}")
                click.secho(f"  Name: {r.name}")
                click.secho(f"  Owner: {r.owner}")
                click.secho(f"  Repo: {r.repo}")
                click.secho(f"  Latest Tag: {tag}")
                click.secho(f"  Last Fetched: {r.last_fetched or 'Never'}")
            else:
                click.secho(f"{r.id[:8]}... | {r.name[:40]} | {tag}")
    except Exception as e:
        click.secho(f"Error: Failed to list repos: {e}", err=True, fg="red")
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
            click.secho(f"Removed repo: {repo_id}", fg="green")
        else:
            click.secho(f"Repo not found: {repo_id}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to remove repo: {e}", err=True, fg="red")
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
                click.secho(f"New release: {release.tag_name}", fg="green")
                if verbose and release.name:
                    click.secho(f"Title: {release.name}")
            elif result.get("error"):
                click.secho(f"Error: {result['error']}", fg="red")
                if "rate limit" in result["error"].lower():
                    click.secho("Hint: Set GITHUB_TOKEN environment variable for 5000 req/hour", fg="yellow")
                sys.exit(1)
            else:
                click.secho(result.get("message", "No new release"), fg="yellow")
        else:
            # Refresh all repos
            repos = list_github_repos()
            if not repos:
                click.secho("No GitHub repos monitored. Use 'repo add <url>' first.")
                return

            new_release_count = 0
            for r in repos:
                try:
                    result = refresh_github_repo(r.id)
                    if result.get("new_release"):
                        new_release_count += 1
                        click.secho(f"New release for {r.name}: {result['release'].tag_name}", fg="green")
                    elif result.get("error"):
                        click.secho(f"Error refreshing {r.name}: {result['error']}", fg="yellow")
                except Exception as e:
                    click.secho(f"Error refreshing {r.name}: {e}", fg="yellow")

            if new_release_count > 0:
                click.secho(f"\nFetched {new_release_count} new release(s)", fg="green")
            else:
                click.secho("No new releases found")

    except RepoNotFoundError:
        click.secho(f"Repo not found: {repo_id}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to refresh repos: {e}", err=True, fg="red")
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
                click.secho("No GitHub repos monitored. Use 'repo add <url>' first.")
                return

            click.secho("Select a repo to view changelog:")
            for i, r in enumerate(repos, 1):
                click.secho(f"  {i}. {r.name}")
            click.secho()

            # For now, show changelog for first repo with stored changelog
            for r in repos:
                changelog = get_repo_changelog(r.id)
                if changelog:
                    _display_changelog(r, changelog, verbose)
                    return

            click.secho("No changelogs stored yet. Use 'repo changelog <id> --refresh' to fetch.")

    except RepoNotFoundError:
        click.secho(f"Repo not found: {repo_id}", fg="red")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
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
        click.secho(f"Repo not found: {repo_id}", fg="red")
        sys.exit(1)

    if refresh:
        # Refresh changelog first
        result = refresh_changelog(repo_id)
        if result.get("error"):
            click.secho(f"Error refreshing changelog: {result['error']}", fg="red")
            # Fall through to show stored changelog if available
        elif result.get("changelog_found"):
            click.secho(f"Changelog refreshed: {result.get('filename', 'unknown')}", fg="green")
        else:
            click.secho(f"No changelog found: {result.get('message', 'unknown')}", fg="yellow")
            return

    # Get stored changelog
    changelog = get_repo_changelog(repo_id)
    if changelog:
        _display_changelog(repo, changelog, verbose)
    else:
        click.secho(f"No changelog stored for {repo.name}. Use --refresh to fetch.", fg="yellow")


def _display_changelog(repo, changelog: dict, verbose: bool) -> None:
    """Display a changelog article.

    Args:
        repo: GitHubRepo object.
        changelog: Dict with title, link, content, created_at.
        verbose: Whether to show full content or just header.
    """
    click.secho(f"\n=== {changelog['title']} ===")
    click.secho(f"Source: {changelog['link']}")
    click.secho(f"Stored: {changelog['created_at']}")
    click.secho()

    if verbose:
        # Show full content
        click.secho(changelog['content'])
    else:
        # Show first 2000 characters
        content = changelog['content']
        if len(content) > 2000:
            click.secho(content[:2000])
            click.secho(f"\n... (truncated, use --verbose for full content)")
        else:
            click.secho(content)


@cli.group()
@click.pass_context
def tag(ctx: click.Context) -> None:
    """Manage article tags."""
    pass


@tag.command("add")
@click.argument("name")
@click.pass_context
def tag_add(ctx: click.Context, name: str) -> None:
    """Create a new tag."""
    try:
        t = add_tag(name)
        click.secho(f"Created tag: {t.name}", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@tag.command("list")
@click.pass_context
def tag_list(ctx: click.Context) -> None:
    """List all tags with article counts."""
    try:
        tags = list_tags()
        counts = get_tag_article_counts()
        if not tags:
            click.secho("No tags created yet. Use 'tag add <name>' to create one.")
            return
        click.secho("Tag | Articles")
        click.secho("-" * 30)
        for t in tags:
            count = counts.get(t.name, 0)
            click.secho(f"{t.name} | {count}")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@tag.command("remove")
@click.argument("tag_name")
@click.pass_context
def tag_remove(ctx: click.Context, tag_name: str) -> None:
    """Remove a tag (unlinks from all articles)."""
    try:
        removed = remove_tag(tag_name)
        if removed:
            click.secho(f"Removed tag: {tag_name}", fg="green")
        else:
            click.secho(f"Tag not found: {tag_name}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@tag.group()
@click.pass_context
def rule(ctx: click.Context) -> None:
    """Manage tag rules for automatic tagging."""
    pass


@rule.command("add")
@click.argument("tag_name")
@click.option("--keyword", "-k", multiple=True, help="Keyword to match (can specify multiple)")
@click.option("--regex", "-r", help="Regex pattern to match")
@click.pass_context
def tag_rule_add(ctx: click.Context, tag_name: str, keyword: tuple, regex: Optional[str]) -> None:
    """Add a rule for a tag (D-07).

    Examples:
        tag rule add AI --keyword "machine learning" --keyword "deep learning"
        tag rule add Security --regex "CVE-\\d+"
    """
    if not keyword and not regex:
        click.secho("Error: Must specify --keyword or --regex", fg="red")
        sys.exit(1)
    try:
        add_rule(tag_name, keywords=list(keyword) if keyword else None, regex=[regex] if regex else None)
        click.secho(f"Added rule(s) for tag '{tag_name}'", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@rule.command("remove")
@click.argument("tag_name")
@click.option("--keyword", "-k", help="Keyword to remove")
@click.option("--regex", "-r", help="Regex pattern to remove")
@click.pass_context
def tag_rule_remove(ctx: click.Context, tag_name: str, keyword: Optional[str], regex: Optional[str]) -> None:
    """Remove a rule from a tag."""
    if not keyword and not regex:
        click.secho("Error: Must specify --keyword or --regex", fg="red")
        sys.exit(1)
    try:
        removed = remove_rule(tag_name, keyword=keyword, regex_pattern=regex)
        if removed:
            click.secho(f"Removed rule from '{tag_name}'", fg="green")
        else:
            click.secho(f"Rule not found for '{tag_name}'", fg="yellow")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@rule.command("list")
@click.pass_context
def tag_rule_list(ctx: click.Context) -> None:
    """List all tag rules."""
    try:
        rules = list_rules()
        tags = rules.get("tags", {})
        if not tags:
            click.secho("No tag rules defined. Use 'tag rule add' to create one.")
            return
        click.secho("Tag Rules:")
        click.secho("=" * 50)
        for tag_name, rule in tags.items():
            click.secho(f"\n{tag_name}:")
            for kw in rule.get("keywords", []):
                click.secho(f"  [keyword] {kw}")
            for pattern in rule.get("regex", []):
                click.secho(f"  [regex] {pattern}")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@rule.command("edit")
@click.argument("tag_name")
@click.option("--add-keyword", "-k", multiple=True, help="Keyword to add (can specify multiple)")
@click.option("--remove-keyword", "-K", multiple=True, help="Keyword to remove (can specify multiple)")
@click.option("--add-regex", "-r", multiple=True, help="Regex pattern to add (can specify multiple)")
@click.option("--remove-regex", "-R", multiple=True, help="Regex pattern to remove (can specify multiple)")
@click.pass_context
def tag_rule_edit(ctx: click.Context, tag_name: str, add_keyword: tuple, remove_keyword: tuple, add_regex: tuple, remove_regex: tuple) -> None:
    """Edit a tag rule by adding/removing keywords or regex patterns (D-07).

    Examples:
        tag rule edit AI --add-keyword "neural network"
        tag rule edit Security --remove-keyword "vulnerability" --add-regex "CVE-\\\\d+"
    """
    if not add_keyword and not remove_keyword and not add_regex and not remove_regex:
        click.secho("Error: Must specify at least one of --add-keyword, --remove-keyword, --add-regex, or --remove-regex", fg="red")
        sys.exit(1)

    try:
        success = edit_rule(
            tag_name,
            add_keywords=list(add_keyword) if add_keyword else None,
            remove_keywords=list(remove_keyword) if remove_keyword else None,
            add_regex=list(add_regex) if add_regex else None,
            remove_regex=list(remove_regex) if remove_regex else None
        )
        if success:
            click.secho(f"Updated rule for tag '{tag_name}'", fg="green")
        else:
            click.secho(f"Rule not found for tag '{tag_name}'", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


if __name__ == "__main__":
    cli()
