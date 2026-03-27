"""Article management commands for RSS reader CLI."""

import sys
import platform
import subprocess
import logging
import importlib.machinery
import pathlib
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.application.articles import get_article_detail, list_articles, search_articles
from src.storage import search_articles_semantic, get_related_articles

logger = logging.getLogger(__name__)

# Import run_auto_tagging from src/tags/ai_tagging.py module
_ai_tagging_module_path = pathlib.Path(__file__).parent.parent / "tags" / "ai_tagging.py"
_loader = importlib.machinery.SourceFileLoader("src_ai_tagging_module", str(_ai_tagging_module_path))
_spec = importlib.util.spec_from_loader("src_ai_tagging_module", _loader)
_ai_tagging_module = importlib.util.module_from_spec(_spec)
_loader.exec_module(_ai_tagging_module)
run_auto_tagging = _ai_tagging_module.run_auto_tagging


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
        from src.application.articles import list_articles_with_tags, get_articles_with_tags
        articles = list_articles_with_tags(limit=limit, feed_id=feed_id, tag=tag, tags=tags)
        if not articles:
            click.secho("No articles found. Add some feeds and fetch them first.")
            return

        # Batch fetch tags for all articles
        article_ids = [a.id for a in articles]
        tags_map = get_articles_with_tags(article_ids)

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
        # Run AI clustering
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
            from src.storage import get_untagged_articles
            untagged = get_untagged_articles()

            if not untagged:
                click.secho("No untagged articles found.", fg="yellow")
                return

            click.secho(f"Applying rules to {len(untagged)} untagged articles...", fg="cyan")
            applied_count = 0
            from src.tags.tag_rules import apply_rules_to_article
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
        # Manual tagging
        try:
            from src.storage.sqlite import tag_article
            tagged = tag_article(article_id, tag_name)
            if tagged:
                click.secho(f"Tagged article {article_id} with '{tag_name}'", fg="green")
            else:
                click.secho(f"Failed to tag article", fg="red")
                sys.exit(1)
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
            click.secho("Semantic search results (by similarity):")
            click.secho("-" * 80)
            for i, result in enumerate(results):
                title = result.get("title") or "No title"
                url = result.get("url") or ""
                distance = result.get("distance")
                # Convert L2 distance to cosine similarity for normalized embeddings:
                # L2_dist = sqrt(2 - 2*cos_sim) => cos_sim = 1 - dist^2/2
                if distance is not None:
                    cos_sim = max(0.0, 1.0 - (distance * distance / 2.0))
                    similarity = f"{round(cos_sim * 100, 1)}%"
                else:
                    similarity = "N/A"
                if verbose:
                    click.secho(f"\nTitle: {title}")
                    sqlite_id = result.get("sqlite_id")
                    if sqlite_id:
                        click.secho(f"ID: {sqlite_id[:8]}")
                    click.secho(f"URL: {url}")
                    click.secho(f"Similarity: {similarity}")
                    doc = result.get("document") or ""
                    if doc:
                        preview = doc[:150] + "..." if len(doc) > 150 else doc
                        click.secho(f"Content preview: {preview}")
                else:
                    sqlite_id = result.get("sqlite_id")
                    id_display = f"{sqlite_id[:8]} | " if sqlite_id else ""
                    click.secho(f"{id_display}{title[:40]} | Similarity: {similarity}")
        else:
            # FTS5 keyword search
            articles = search_articles(query=query, limit=limit, feed_id=feed_id)
            if not articles:
                click.secho("No articles found matching your search.")
                return

            click.secho("Title | Source | Date")
            click.secho("-" * 80)

            for article in articles:
                title = article.title or "No title"
                pub_date = article.pub_date or "No date"

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
