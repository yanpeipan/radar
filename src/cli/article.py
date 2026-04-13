"""Article management commands for Radar CLI."""

import logging
import os
import platform
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.application.article_view import fetch_and_fill_article, fetch_url_content
from src.application.articles import ArticleListItem, get_article_detail, list_articles
from src.cli.ui import (
    format_article_list,
    print_json,
    print_json_error,
)
from src.storage import list_articles_by_tag

logger = logging.getLogger(__name__)


def _format_date(published_at: int | str | None) -> str:
    """Format published_at as 'YYYY-MM-DD' or return '-'."""
    if published_at is None:
        return "-"
    if isinstance(published_at, int):
        from datetime import datetime

        from src.application.config import get_timezone

        tz = get_timezone()
        dt = datetime.fromtimestamp(published_at, tz=tz)
        return dt.strftime("%Y-%m-%d")
    if isinstance(published_at, str):
        # Handle 'YYYY-MM-DD HH:MM:SS' format
        if len(published_at) >= 10:
            return published_at[:10]
        return published_at
    return "-"


def print_articles(items: list[ArticleListItem]) -> None:
    """Print formatted articles to console using Rich Table.

    Args:
        items: List of ArticleListItem objects.
    """
    console = Console()

    if not items:
        click.secho("No articles found.")
        return

    table = Table(
        show_header=True,
        header_style="bold magenta",
        expand=False,
        row_styles=["", "dim"],
    )
    table.add_column("ID", style="dim", width=8, no_wrap=True, overflow="ellipsis")
    table.add_column(
        "Title", style="cyan", min_width=30, max_width=70, overflow="ellipsis"
    )
    table.add_column(
        "Source", style="green", width=12, no_wrap=True, overflow="ellipsis"
    )
    table.add_column(
        "Date", style="yellow", width=12, no_wrap=True, overflow="ellipsis"
    )

    for item in items:
        title = item.title[:80] if item.title else "-"
        if item.link:
            title = f"[link={item.link}]{title}[/link]"

        table.add_row(
            (item.id[:8] if item.id else "-"),
            title,
            (item.feed_name[:15] if item.feed_name else "-"),
            _format_date(item.published_at),
        )

    console.print(table)


def open_in_browser(url: str) -> None:
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", url])
    elif system == "Linux":
        subprocess.run(["xdg-open", url])
    elif system == "Windows":
        os.startfile(url)  # nosec B602 - safe alternative to subprocess with shell=True
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


from src.cli import cli  # noqa: E402


@cli.group()
@click.pass_context
def article(ctx: click.Context) -> None:
    """Manage articles."""
    pass


@article.command("list")
@click.option("--limit", default=20, help="Maximum number of articles to show")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.option("--since", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--until", default=None, help="End date (YYYY-MM-DD)")
@click.option("--on", multiple=True, help="Specific date (YYYY-MM-DD), can repeat")
@click.option(
    "--groups", default=None, help="Filter by feed groups (comma-separated, OR logic)"
)
@click.option(
    "--tag",
    default=None,
    help="Filter by tag name (articles from feeds with this tag)",
)
@click.option(
    "--sort",
    default=None,
    type=click.Choice(["quality"]),
    help="Sort by quality (requires --min-quality to be useful; sorts by quality_score DESC)",
)
@click.option(
    "--min-quality",
    default=None,
    type=float,
    help="Filter to articles with quality_score >= value (0.0-1.0)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def article_list(
    ctx: click.Context,
    limit: int,
    feed_id: str | None,
    since: str | None,
    until: str | None,
    on: tuple,
    groups: str | None,
    tag: str | None,
    sort: str | None,
    min_quality: float | None,
    json_output: bool,
) -> None:
    """List recent articles from all feeds or a specific feed."""
    try:
        on_list = list(on) if on else None
        groups_list = groups.split(",") if groups else None
        if tag:
            articles = list_articles_by_tag(tag, limit=limit)
        else:
            articles = list_articles(
                limit=limit,
                feed_id=feed_id,
                since=since,
                until=until,
                on=on_list,
                groups=groups_list,
                sort_by=sort,
                min_quality=min_quality,
            )
        if json_output:
            print_json(format_article_list(articles, limit))
            return
        print_articles(articles)
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to list articles: {e}", "list_error")
            return
        click.secho(f"Error: Failed to list articles: {e}", err=True, fg="red")
        logger.exception("Failed to list articles")
        sys.exit(1)


@article.command("view")
@click.option("--url", "url_arg", default=None, help="URL to fetch and extract content")
@click.option(
    "--id", "id_arg", default=None, help="Article ID to fetch and fill content"
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.argument("article_id", required=False)
@click.pass_context
def article_view(
    ctx: click.Context,
    url_arg: str | None,
    id_arg: str | None,
    json_output: bool,
    article_id: str | None,
) -> None:
    """View article content. Use --url to fetch a URL, --id to fetch from DB, or provide ARTICLE_ID for existing content."""
    # Mutual exclusivity check
    if url_arg and id_arg:
        if json_output:
            print_json_error(
                "Cannot use both --url and --id", "mutual_exclusion", exit_code=1
            )
        click.secho("Error: Cannot use both --url and --id", err=True, fg="red")
        sys.exit(1)

    try:
        if url_arg:
            # --url mode: fetch directly
            result = fetch_url_content(url_arg)
            if "error" in result:
                if json_output:
                    print_json_error(result["error"], "fetch_error", exit_code=1)
                click.secho(f"Error: {result['error']}", err=True, fg="red")
                sys.exit(1)
            if json_output:
                print_json(result)
                return
            _print_content_view(result)

        elif id_arg:
            # --id mode: fetch from DB and fill
            result = fetch_and_fill_article(id_arg)
            if "error" in result:
                if json_output:
                    print_json_error(result["error"], "fetch_error", exit_code=1)
                click.secho(f"Error: {result['error']}", err=True, fg="red")
                sys.exit(1)
            if json_output:
                print_json(result)
                return
            _print_content_view(result)

        else:
            # Legacy mode: view existing article from DB
            if not article_id:
                if json_output:
                    print_json_error(
                        "ARTICLE_ID required when not using --url or --id",
                        "missing_arg",
                        exit_code=1,
                    )
                click.secho(
                    "Error: ARTICLE_ID required when not using --url or --id",
                    err=True,
                    fg="red",
                )
                sys.exit(1)
            # Call original logic - reuse get_article_detail
            article = get_article_detail(article_id)
            if not article:
                if json_output:
                    print_json_error(
                        f"Article not found: {article_id}", "not_found", exit_code=1
                    )
                click.secho(f"Article not found: {article_id}", fg="red")
                sys.exit(1)
            if json_output:
                print_json(article)
                return
            # Existing rich output for legacy mode
            console = Console()
            meta_table = Table(show_header=False, box=None)
            meta_table.add_row("Source:", article["feed_name"] or "Unknown")
            meta_table.add_row("Type:", article.get("source_type", "feed").capitalize())
            meta_table.add_row("Date:", _format_date(article["published_at"]))
            link = article["link"] or "No link"
            meta_table.add_row("Link:", link)
            title = article["title"] or "No title"
            console.print(
                Panel(
                    meta_table,
                    title=title,
                    subtitle=f"{article['feed_name']} | {_format_date(article['published_at'])}",
                )
            )
            if article["content"]:
                console.print()
                console.print(article["content"])
            else:
                console.print(
                    Panel("[dim]No content available[/dim]", border_style="yellow")
                )
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to view article: {e}", "view_error")
            return
        click.secho(f"Error: Failed to view article: {e}", err=True, fg="red")
        logger.exception("Failed to view article")
        sys.exit(1)


def _print_content_view(result: dict) -> None:
    """Print content view result in rich format."""
    console = Console()
    title = result.get("title") or "No title"
    url = result.get("url") or ""
    extracted_at = result.get("extracted_at", "")
    console.print(
        Panel(result["content"], title=title, subtitle=f"{url} | {extracted_at}")
    )


@article.command("open")
@click.argument("article_id")
@click.pass_context
def article_open(ctx: click.Context, article_id: str) -> None:
    try:
        article = get_article_detail(article_id)
        if not article:
            click.secho(f"Article not found: {article_id}", fg="red")
            sys.exit(1)
        link = article.get("link")
        if not link:
            click.secho("No link available for this article", fg="red")
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


@cli.command("search")
@click.argument("query")
@click.option("--limit", default=20, help="Maximum number of results")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.option(
    "--semantic", is_flag=True, help="Use semantic search instead of keyword search"
)
@click.option(
    "--cross-encoder", is_flag=True, help="Apply Cross-Encoder reranking to results"
)
@click.option("--since", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--until", default=None, help="End date (YYYY-MM-DD)")
@click.option("--on", multiple=True, help="Specific date (YYYY-MM-DD), can repeat")
@click.option(
    "--groups", default=None, help="Filter by feed groups (comma-separated, OR logic)"
)
@click.option(
    "--tag",
    default=None,
    help="Filter by tag name (articles from feeds with this tag)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def article_search(
    ctx: click.Context,
    query: str,
    limit: int,
    feed_id: str | None,
    semantic: bool,
    cross_encoder: bool,
    since: str | None,
    until: str | None,
    on: tuple,
    groups: str | None,
    tag: str | None,
    json_output: bool,
) -> None:
    try:
        from src.application.articles import (
            search_articles_fts,
            search_articles_semantic,
        )

        on_list = list(on) if on else None
        groups_list = groups.split(",") if groups else None

        if semantic:
            try:
                articles = search_articles_semantic(
                    query_text=query,
                    limit=limit,
                    since=since,
                    until=until,
                    on=on_list,
                    groups=groups_list,
                    tag=tag,
                    cross_encoder=cross_encoder,
                )
            except RuntimeError as e:
                if json_output:
                    print_json_error(
                        f"Semantic search unavailable: {e}", "ml_dependency_error"
                    )
                    return
                click.secho(f"Semantic search unavailable: {e}", err=True, fg="yellow")
                sys.exit(1)
        else:
            articles = search_articles_fts(
                query=query,
                limit=limit,
                feed_id=feed_id,
                since=since,
                until=until,
                on=on_list,
                groups=groups_list,
                tag=tag,
                cross_encoder=cross_encoder,
            )

        if json_output:
            print_json(format_article_list(articles, limit))
            return
        print_articles(articles)
    except Exception as e:
        if json_output:
            print_json_error(f"Search unavailable: {e}", "search_error")
            return
        click.secho(f"Search unavailable: {e}.", err=True, fg="yellow")
        logger.exception("Failed to search articles")
        sys.exit(1)


@article.command("related")
@click.argument("article-id")
@click.option("--limit", default=5, help="Maximum number of related articles")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def article_related(
    ctx: click.Context, article_id: str, limit: int, json_output: bool
) -> None:
    try:
        # Lazy import to avoid torch dependency when not using related articles
        from src.application.related import get_related_articles

        articles = get_related_articles(article_id=article_id, limit=limit)
        if json_output:
            print_json(format_article_list(articles, limit))
            return
        print_articles(articles)
    except Exception as e:
        if json_output:
            print_json_error(f"Failed to find related articles: {e}", "related_error")
            return
        click.secho(f"Error: Failed to find related articles: {e}", err=True, fg="red")
        logger.exception("Failed to find related articles")
        sys.exit(1)
