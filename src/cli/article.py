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
from src.application.search import format_semantic_results, format_fts_results, rank_semantic_results, rank_list_results, rank_fts_results, format_articles, print_articles
# Lazy import: from src.application.related import get_related_articles_display
# Lazy import: from src.storage.vector import search_articles_semantic

logger = logging.getLogger(__name__)



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
        ranked = rank_list_results(articles)
        formatted = format_articles(ranked, verbose=verbose)
        print_articles(formatted, verbose=verbose)
    except Exception as e:
        click.secho(f"Error: Failed to list articles: {e}", err=True, fg="red")
        logger.exception("Failed to list articles"); sys.exit(1)

@article.command("view")
@click.argument("article_id")
@click.option("--verbose", is_flag=True, help="Show full content without truncation")
@click.pass_context
def article_view(ctx: click.Context, article_id: str, verbose: bool) -> None:
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
            content = article["content"] if verbose else article["content"][:2000]
            if not verbose and len(article["content"]) > 2000: content += "\n\n... (truncated, use --verbose for full content)"
            console.print(); console.print(content)
        else: console.print("\n[yellow]No content available[/yellow]")
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
@click.pass_context
def article_search(ctx: click.Context, query: str, limit: int, feed_id: Optional[str], semantic: bool) -> None:
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        if semantic:
            # Lazy import to avoid torch dependency for non-semantic search
            from src.storage.vector import search_articles_semantic
            results = search_articles_semantic(query_text=query, limit=limit)
            if not results: click.secho("No articles found matching your semantic search."); return
            # Apply multi-factor ranking
            results = rank_semantic_results(results, top_k=limit)
            formatted = format_semantic_results(results, verbose=verbose)
            print_articles(formatted, verbose=verbose)
        else:
            articles = search_articles(query=query, limit=limit, feed_id=feed_id)
            if not articles: click.secho("No articles found matching your search."); return
            ranked = rank_fts_results(articles)
            formatted = format_articles(ranked, verbose=verbose)
            print_articles(formatted, verbose=verbose)
    except Exception as e:
        click.secho(f"Search unavailable: {e}.", err=True, fg="yellow")
        logger.exception("Failed to search articles"); sys.exit(1)

@article.command("related")
@click.argument("article-id")
@click.option("--limit", default=5, help="Maximum number of related articles")
@click.pass_context
def article_related(ctx: click.Context, article_id: str, limit: int) -> None:
    verbose = ctx.parent and ctx.parent.obj.get("verbose") if ctx.parent else False
    try:
        # Lazy import to avoid torch dependency when not using related articles
        from src.application.related import get_related_articles_display
        results = get_related_articles_display(article_id=article_id, limit=limit, verbose=verbose)
        if not results: click.secho("No related articles found."); return
        if results and results[0].get("no_embedding"):
            click.secho("Article was fetched before v1.8 and has no semantic embedding. Fetch the article again to enable similarity search.", fg="yellow"); return
        click.secho(f"Articles related to {article_id}:\n" + "-" * 80)
        for item in results:
            if verbose:
                click.secho(f"\nTitle: {item['title']}\nURL: {item['url']}\nSimilarity: {item['similarity']}")
                if item.get('document_preview'): click.secho(f"Content preview: {item['document_preview']}")
            else: click.secho(f"{item['title'][:50]} | Similarity: {item['similarity']}")
    except Exception as e:
        click.secho(f"Error: Failed to find related articles: {e}", err=True, fg="red")
        logger.exception("Failed to find related articles"); sys.exit(1)
