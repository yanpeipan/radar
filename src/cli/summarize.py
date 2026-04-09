"""Summarize command — LLM-powered article summarization, quality scoring, keyword extraction."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from src.cli import cli
from src.cli.ui import print_json, print_json_error
from src.storage import list_articles_for_llm

logger = logging.getLogger(__name__)
console = Console()


def _resolve_article_ids(
    url: str | None,
    article_id: str | None,
    group: str | None,
    feed_id: str | None,
    all_: bool,
    limit: int,
) -> tuple[list | None, str]:
    """Resolve CLI arguments into a list of article IDs and a mode string.

    Returns (article_ids_or_none, mode). mode is used for dry-run messaging.
    """
    # Count of mutually exclusive args
    sources = sum(1 for x in [url, article_id, group, feed_id, all_] if x)

    if sources == 0:
        return None, "no filter"
    if sources > 1:
        return None, "multiple (mutually exclusive)"

    if url:
        return None, "url"
    if article_id:
        return [article_id], "id"
    if group:
        articles = list_articles_for_llm(limit=limit, groups=[group])
        return [a["id"] for a in articles], f"group:{group}"
    if feed_id:
        articles = list_articles_for_llm(limit=limit, feed_id=feed_id)
        return [a["id"] for a in articles], f"feed:{feed_id}"
    if all_:
        articles = list_articles_for_llm(limit=limit)
        return [a["id"] for a in articles], "all feeds"


@cli.command("summarize")
@click.option("--url", default=None, help="Summarize article at URL directly (no DB)")
@click.option("--id", "article_id", default=None, help="Summarize article by ID")
@click.option("--group", default=None, help="Summarize all articles in this group")
@click.option(
    "--feed-id", "feed_id", default=None, help="Summarize all articles in feed"
)
@click.option("--all", "all_", is_flag=True, help="Summarize all unsummarized articles")
@click.option(
    "--force", is_flag=True, help="Re-summarize even if article already has summary"
)
@click.option("--dry-run", is_flag=True, help="Preview articles without calling LLM")
@click.option(
    "--json", "json_output", is_flag=True, help="Machine-readable JSON output"
)
@click.option(
    "--limit",
    default=50,
    help="Max articles to process in batch mode (default: 50)",
)
@click.pass_context
def summarize(
    ctx: click.Context,
    url: str | None,
    article_id: str | None,
    group: str | None,
    feed_id: str | None,
    all_: bool,
    force: bool,
    dry_run: bool,
    json_output: bool,
    limit: int,
) -> None:
    """Summarize articles using LLM with quality scoring and keyword extraction.

    Requires one of: --url, --id, --group, --feed-id, --all

    Examples:

        feedship summarize --id abc12345
        feedship summarize --group AI --force
        feedship summarize --all --limit 100
        feedship summarize --url https://example.com/article
    """
    # Validate mutually exclusive options
    sources = sum(1 for x in [url, article_id, group, feed_id, all_] if x)
    if sources == 0:
        if json_output:
            print_json_error(
                "Specify one of: --url, --id, --group, --feed-id, --all",
                "missing_filter",
                exit_code=1,
            )
        click.secho(
            "Error: Specify one of: --url, --id, --group, --feed-id, --all",
            err=True,
            fg="red",
        )
        sys.exit(1)

    if sources > 1:
        if json_output:
            print_json_error(
                "Use only one of: --url, --id, --group, --feed-id, --all",
                "mutual_exclusion",
                exit_code=1,
            )
        click.secho(
            "Error: Use only one of: --url, --id, --group, --feed-id, --all",
            err=True,
            fg="red",
        )
        sys.exit(1)

    # URL mode: fetch directly, no DB needed
    if url:
        _summarize_url(url, json_output)
        return

    # Resolve article IDs from DB
    article_ids, mode_label = _resolve_article_ids(
        url, article_id, group, feed_id, all_, limit
    )

    if article_ids is None:
        if json_output:
            print_json_error(mode_label, "invalid_args", exit_code=1)
        click.secho(f"Error: {mode_label}", err=True, fg="red")
        sys.exit(1)

    if len(article_ids) == 0:
        if json_output:
            print_json(
                {"success": True, "message": "No articles to process", "count": 0}
            )
        else:
            click.secho("No articles to process.", fg="yellow")
        return

    if dry_run:
        _dry_run(article_ids, mode_label, json_output)
        return

    # Process articles
    _process_batch(article_ids, force, json_output)


def _summarize_url(url: str, json_output: bool) -> None:
    """Summarize an article fetched directly from URL."""
    from src.application.article_view import fetch_url_content
    from src.application.llm import extract_keywords, score_quality, summarize_text

    result = fetch_url_content(url)
    if "error" in result:
        if json_output:
            print_json_error(result["error"], "fetch_error", exit_code=1)
        click.secho(f"Error: {result['error']}", err=True, fg="red")
        sys.exit(1)

    title = result.get("title", "")
    content = result.get("content", "")

    if not content:
        if json_output:
            print_json_error("No content extracted from URL", "no_content", exit_code=1)
        click.secho("Error: No content extracted from URL", err=True, fg="red")
        sys.exit(1)

    if json_output:
        console.print("[yellow]Generating summary...[/yellow]")

    async def run():
        summary, was_truncated = await summarize_text(content, title)
        quality = await score_quality(content, title)
        keywords = await extract_keywords(content, max_keywords=5)
        return summary, was_truncated, quality, keywords

    summary, was_truncated, quality, keywords = asyncio.run(run())

    if json_output:
        print_json(
            {
                "url": url,
                "title": title,
                "summary": summary,
                "quality_score": quality,
                "keywords": keywords,
                "was_truncated": was_truncated,
            }
        )
        return

    from rich.panel import Panel

    console.print(
        Panel(
            summary,
            title=f"Summary: {title}",
            border_style="cyan",
        )
    )
    console.print(f"Quality score: {quality:.2f}")
    console.print(f"Keywords: {', '.join(keywords)}")
    if was_truncated:
        console.print(
            "[yellow]Note: Content was truncated due to token limits[/yellow]"
        )


def _dry_run(article_ids: list, mode_label: str, json_output: bool) -> None:
    """Preview articles without calling LLM."""
    if json_output:
        print_json(
            {
                "mode": mode_label,
                "count": len(article_ids),
                "article_ids": article_ids,
                "dry_run": True,
            }
        )
        return

    console.print(
        f"[cyan]Dry run — {len(article_ids)} articles would be processed[/cyan]"
    )
    console.print(f"Mode: {mode_label}")
    for aid in article_ids[:20]:
        console.print(f"  • {aid[:8]}")
    if len(article_ids) > 20:
        console.print(f"  ... and {len(article_ids) - 20} more")


def _process_batch(
    article_ids: list[str],
    force: bool,
    json_output: bool,
) -> None:
    """Process articles in batch with progress bar."""
    from src.application.summarize import process_article_llm_batch

    results: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Processing {len(article_ids)} articles...",
            total=len(article_ids),
        )

        async def run_batch():
            batch_results = await process_article_llm_batch(article_ids, force=force)
            for i, r in enumerate(batch_results):
                progress.update(task, completed=i + 1)
                results.append(r)
            return batch_results

        asyncio.run(run_batch())

    # Report results
    if json_output:
        print_json(
            {
                "total": len(results),
                "succeeded": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
                "results": results,
            }
        )
        return

    succeeded = 0
    failed = 0
    for r in results:
        if r.get("success"):
            succeeded += 1
            title = r.get("title", "Unknown")[:60]
            q = r.get("quality_score", 0)
            console.print(
                f"[green]✓[/green] {r['article_id'][:8]} | {title} | q={q:.2f}"
            )
        else:
            failed += 1
            aid = r.get("article_id", "?")[:8]
            err = r.get("error", "Unknown error")[:60]
            console.print(f"[red]✗[/red] {aid} | {err}")

    console.print(f"\n[bold]Done:[/bold] {succeeded} succeeded, {failed} failed")
