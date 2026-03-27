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

from src.application.articles import get_article_detail, list_articles, search_articles
from src.application.search import format_semantic_results, format_fts_results
from src.storage import search_articles_semantic, get_related_articles

logger = logging.getLogger(__name__)


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


# Import cli from parent package
from src.cli import cli


@cli.group()
@click.pass_context
def article(ctx: click.Context) -> None:
    """Manage articles."""
    pass


@article.command("list")
@click.option("--limit", default=20, help="Maximum number of articles to show")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.option("--verbose", is_flag=True, help="Show full article IDs (32 chars)")
@click.pass_context
def article_list(ctx: click.Context, limit: int, feed_id: Optional[str], verbose: bool) -> None:
    """List recent articles from all feeds or a specific feed.

    Use --verbose to show full 32-char article IDs instead of truncated 8-char IDs.
    """
    verbose = verbose or (ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False)
    try:
        articles = list_articles(limit=limit, feed_id=feed_id)
        if not articles:
            click.secho("No articles found. Add some feeds and fetch them first.")
            return

        # Create rich table
        console = Console()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=8 if not verbose else 36)
        table.add_column("Title")
        table.add_column("Source", max_width=20)
        table.add_column("Date", max_width=10)

        for article in articles:
            title = article.title or "No title"
            pub_date = article.pub_date or "No date"

            source = article.feed_name or "Unknown"

            # Use full ID if verbose, otherwise truncate to 8 chars
            id_display = article.id if verbose else article.id[:8]

            table.add_row(id_display, title[:50], source[:20], pub_date[:10])

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
        # First try article
        article = get_article_detail(article_id)

        if not article:
            click.secho(f"Article not found: {article_id}", fg="red")
            sys.exit(1)

        console = Console()

        # Create metadata table
        meta_table = Table(show_header=False, box=None)
        source_type = article.get("source_type", "feed")
        meta_table.add_row("Source:", article["feed_name"] or "Unknown")
        meta_table.add_row("Type:", source_type.capitalize())
        meta_table.add_row("Date:", article["pub_date"] or "No date")

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


@article.command("open")
@click.argument("article_id")
@click.pass_context
def article_open(ctx: click.Context, article_id: str) -> None:
    """Open article URL in default browser. Works for both articles and releases."""
    try:
        article = get_article_detail(article_id)

        if not article:
            click.secho(f"Article not found: {article_id}", fg="red")
            sys.exit(1)

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


@cli.command("search")
@click.argument("query")
@click.option("--limit", default=20, help="Maximum number of results")
@click.option("--feed-id", default=None, help="Filter by feed ID")
@click.option("--semantic", is_flag=True, help="Use semantic search instead of keyword search")
@click.pass_context
def article_search(ctx: click.Context, query: str, limit: int, feed_id: Optional[str], semantic: bool) -> None:
    """Search articles by keyword or semantic similarity.

    Use --semantic for AI-powered similarity search. Without --semantic,
    uses FTS5 full-text search.

    FTS5 query syntax (without --semantic):
    - Multiple words default to AND (all must match)
    - Use quotes for exact phrase: "machine learning"
    - Use OR for either: python OR ruby
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        if semantic:
            # Semantic search via ChromaDB
            results = search_articles_semantic(query_text=query, limit=limit)
            if not results:
                click.secho("No articles found matching your semantic search.")
                return
            formatted = format_semantic_results(results, verbose=verbose)
            click.secho("Semantic search results (by similarity):")
            click.secho("-" * 80)
            for item in formatted:
                if verbose:
                    click.secho(f"\nTitle: {item['title']}")
                    if item['id_display']:
                        click.secho(f"ID: {item['id_display']}")
                    if item['url']:
                        click.secho(f"URL: {item['url']}")
                    click.secho(f"Similarity: {item['similarity']}")
                    if item.get('document_preview'):
                        click.secho(f"Content preview: {item['document_preview']}")
                else:
                    click.secho(f"{item['id_display']}{item['title'][:40]} | Similarity: {item['similarity']}")
        else:
            # FTS5 keyword search
            articles = search_articles(query=query, limit=limit, feed_id=feed_id)
            if not articles:
                click.secho("No articles found matching your search.")
                return

            formatted = format_fts_results(articles, verbose=verbose)
            click.secho("Title | Source | Date")
            click.secho("-" * 80)

            for item in formatted:
                if verbose:
                    click.secho(f"\nTitle: {item['title']}")
                    click.secho(f"Source: {item['source']}")
                    click.secho(f"Date: {item['date']}")
                    if item.get('link'):
                        click.secho(f"Link: {item['link']}")
                    if item.get('description_preview'):
                        click.secho(f"Description: {item['description_preview']}")
                else:
                    click.secho(f"{item['title']} | {item['source']} | {item['date']}")
    except Exception as e:
        click.secho(f"Semantic search unavailable: {e}. Your articles are still stored and searchable by keyword.", err=True, fg="yellow")
        logger.exception("Failed to search articles")
        sys.exit(1)


@article.command("related")
@click.argument("article-id")
@click.option("--limit", default=5, help="Maximum number of related articles")
@click.pass_context
def article_related(ctx: click.Context, article_id: str, limit: int) -> None:
    """Find articles semantically similar to the given article.

    Uses ChromaDB similarity search to find related articles based on
    content embeddings.
    """
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        results = get_related_articles(article_id=article_id, limit=limit)
        if not results:
            # Check if article exists but has no embedding
            from src.storage.sqlite import get_article
            article = get_article(article_id)
            if article:
                click.secho(f"Article was fetched before v1.8 and has no semantic embedding. Fetch the article again to enable similarity search.", fg="yellow")
            else:
                click.secho("No related articles found.")
            return

        click.secho(f"Articles related to {article_id}:")
        click.secho("-" * 80)

        for result in results:
            title = result.get("title") or "No title"
            url = result.get("url") or ""
            distance = result.get("distance")
            similarity = f"{max(0, round((1 - distance) * 100, 1))}%" if distance is not None else "N/A"

            if verbose:
                click.secho(f"\nTitle: {title}")
                click.secho(f"URL: {url}")
                click.secho(f"Similarity: {similarity}")
                doc = result.get("document") or ""
                if doc:
                    preview = doc[:150] + "..." if len(doc) > 150 else doc
                    click.secho(f"Content preview: {preview}")
            else:
                click.secho(f"{title[:50]} | Similarity: {similarity}")
    except Exception as e:
        click.secho(f"Error: Failed to find related articles: {e}", err=True, fg="red")
        logger.exception("Failed to find related articles")
        sys.exit(1)
