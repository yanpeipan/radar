"""Article management commands for RSS reader CLI."""

import sys
import platform
import subprocess
import logging
from typing import Optional
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.application.articles import get_article_detail, list_articles, search_articles, ArticleListItem

logger = logging.getLogger(__name__)


def _format_date(pub_date: int | str | None) -> str:
    """Format pub_date as 'YYYY-MM-DD' or return '-'."""
    if pub_date is None:
        return "-"
    if isinstance(pub_date, int):
        from datetime import datetime
        from src.application.config import get_timezone
        tz = get_timezone()
        dt = datetime.fromtimestamp(pub_date, tz=tz)
        return dt.strftime("%Y-%m-%d")
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

    table = Table(show_header=True, header_style="bold magenta", expand=False, row_styles=["", "dim"])
    table.add_column("ID", style="dim", width=8, no_wrap=True, overflow="ellipsis")
    table.add_column("Title", style="cyan", min_width=30, max_width=70, overflow="ellipsis")
    table.add_column("Source", style="green", width=12, no_wrap=True, overflow="ellipsis")
    table.add_column("Date", style="yellow", width=12, no_wrap=True, overflow="ellipsis")

    for item in items:
        title = item.title[:80] if item.title else "-"
        if item.link:
            title = f"[link={item.link}]{title}[/link]"

        table.add_row(
            (item.id[:8] if item.id else "-"),
            title,
            (item.feed_name[:15] if item.feed_name else "-"),
            _format_date(item.pub_date),
        )

    console.print(table)


def open_in_browser(url: str) -> None:
    system = platform.system()
    if system == "Darwin": subprocess.run(["open", url])
    elif system == "Linux": subprocess.run(["xdg-open", url])
    elif system == "Windows": subprocess.run(["start", "", url], shell=True)
    else: raise RuntimeError(f"Unsupported platform: {system}")

from src.cli import cli

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
@click.pass_context

def article_list(ctx: click.Context, limit: int, feed_id: Optional[str], since: Optional[str], until: Optional[str], on: tuple) -> None:
    """List recent articles from all feeds or a specific feed."""
    try:
        on_list = list(on) if on else None
        articles = list_articles(limit=limit, feed_id=feed_id, since=since, until=until, on=on_list)
        print_articles(articles)
    except Exception as e:
        click.secho(f"Error: Failed to list articles: {e}", err=True, fg="red")
        logger.exception("Failed to list articles"); sys.exit(1)

@article.command("view")
@click.argument("article_id")
@click.pass_context
def article_view(ctx: click.Context, article_id: str) -> None:
    try:
        article = get_article_detail(article_id)
        if not article: click.secho(f"Article not found: {article_id}", fg="red"); sys.exit(1)
        console = Console()
        meta_table = Table(show_header=False, box=None)
        meta_table.add_row("Source:", article["feed_name"] or "Unknown")
        meta_table.add_row("Type:", article.get("source_type", "feed").capitalize())
        meta_table.add_row("Date:", article["pub_date"] or "No date")


        # Link
        link = article["link"] or "No link"
        meta_table.add_row("Link:", link)

        # Display panel with title
        title = article["title"] or "No title"
        console.print(Panel(meta_table, title=title, subtitle=f"{article['feed_name']} | {article['pub_date'] or 'No date'}"))
        if article["content"]:
            console.print(); console.print(article["content"])
        else:
            console.print(Panel("[dim]No content available[/dim]", border_style="yellow"))
    except Exception as e:
        click.secho(f"Error: Failed to view article: {e}", err=True, fg="red")
        logger.exception("Failed to view article"); sys.exit(1)

@article.command("open")
@click.argument("article_id")
@click.pass_context
def article_open(ctx: click.Context, article_id: str) -> None:
    try:
        article = get_article_detail(article_id)
        if not article: click.secho(f"Article not found: {article_id}", fg="red"); sys.exit(1)
        link = article.get("link")
        if not link: click.secho("No link available for this article", fg="red"); sys.exit(1)
        open_in_browser(link); click.secho(f"Opened {link} in browser", fg="green")
    except RuntimeError as e:
        click.secho(f"Error: {e}", err=True, fg="red"); sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Failed to open article: {e}", err=True, fg="red")
        logger.exception("Failed to open article"); sys.exit(1)


@cli.command("search")
@click.argument("query")
@click.option("--limit", default=20, help="Maximum number of results")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.option("--semantic", is_flag=True, help="Use semantic search instead of keyword search")
@click.option("--since", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--until", default=None, help="End date (YYYY-MM-DD)")
@click.option("--on", multiple=True, help="Specific date (YYYY-MM-DD), can repeat")
@click.pass_context
def article_search(ctx: click.Context, query: str, limit: int, feed_id: Optional[str], semantic: bool, since: Optional[str], until: Optional[str], on: tuple) -> None:
    try:
        on_list = list(on) if on else None
        if semantic:
            # Lazy import to avoid torch dependency for non-semantic search
            from src.storage.vector import search_articles_semantic
            articles = search_articles_semantic(query_text=query, limit=limit, since=since, until=until, on=on_list)
        else:
            articles = search_articles(query=query, limit=limit, feed_id=feed_id, since=since, until=until, on=on_list)
        print_articles(articles)
    except Exception as e:
        click.secho(f"Search unavailable: {e}.", err=True, fg="yellow")
        logger.exception("Failed to search articles"); sys.exit(1)

@article.command("related")
@click.argument("article-id")
@click.option("--limit", default=5, help="Maximum number of related articles")
@click.pass_context
def article_related(ctx: click.Context, article_id: str, limit: int) -> None:
    try:
        # Lazy import to avoid torch dependency when not using related articles
        from src.application.related import get_related_articles
        articles = get_related_articles(article_id=article_id, limit=limit)
        print_articles(articles)
    except Exception as e:
        click.secho(f"Error: Failed to find related articles: {e}", err=True, fg="red")
        logger.exception("Failed to find related articles"); sys.exit(1)
