"""Report command — generate structured daily reports from clustered articles."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from src.application.config import get_reports_dir
from src.application.report import ReportData, ReportTemplate
from src.application.report.report_generation import cluster_articles_for_report
from src.cli import cli
from src.cli.ui import print_json, print_json_error

logger = logging.getLogger(__name__)
console = Console()


@cli.command("report")
@click.option("--since", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--until", required=True, help="End date (YYYY-MM-DD)")
@click.option("--output", default=None, help="Save report to file path")
@click.option(
    "--json", "json_output", is_flag=True, help="Machine-readable JSON output"
)
@click.option(
    "--limit",
    default=3333,
    help="Max articles to include in report (default: 3333)",
)
@click.option(
    "--auto-summarize/--no-auto-summarize",
    default=True,
    help="Automatically summarize unsummarized articles on-demand (default: True)",
)
@click.option(
    "--language",
    default="zh",
    type=click.Choice(["zh", "en"]),
    help="Report output language (default: zh)",
)
@click.option(
    "--template",
    "template_name",
    default="ai-daily",
    help="Template name to use (default: ai-daily)",
)
def report(
    since: str,
    until: str,
    output: str | None,
    json_output: bool,
    limit: int,
    auto_summarize: bool,
    language: str,
    template_name: str,
) -> None:
    """Generate a structured daily report from clustered articles.

    Articles are classified into the AI Five-Layer Cake taxonomy and rendered
    using a Jinja2 template.

    Examples:

        feedship report --since 2026-04-01 --until 2026-04-07
        feedship report --since 2026-04-01 --until 2026-04-07 --output report.md
        feedship report --since 2026-04-01 --until 2026-04-07 --json
    """
    try:
        # Cluster articles
        with console.status("[cyan]Fetching and clustering articles..."):
            data = cluster_articles_for_report(
                since=since,
                until=until,
                limit=limit,
                auto_summarize=auto_summarize,
                target_lang=language,
            )
            total_articles = data.total_articles

        if total_articles == 0:
            if json_output:
                print_json(
                    {
                        "success": True,
                        "message": "No articles found in date range",
                        "date_range": {"since": since, "until": until},
                        "total_articles": 0,
                    }
                )
            else:
                console.print(
                    f"[yellow]No articles found for {since} ~ {until}[/yellow]"
                )
                console.print(
                    "Try a different date range or run 'feedship summarize --all' first."
                )
            return

        # Render report
        try:
            report_template = ReportTemplate(template_name=template_name)
            report_text = asyncio.run(report_template.render(data))
        except Exception as e:
            if json_output:
                print_json_error(f"Failed to render template: {e}", "template_error")
            console.print(f"[red]Template error: {e}[/red]")
            sys.exit(1)

        if json_output:
            output_json = {
                "date_range": data.date_range,
                "total_articles": total_articles,
            }
            print_json(output_json)
            return

        # Plain text output
        if output:
            output_path = Path(output)
        else:
            reports_dir = get_reports_dir()
            reports_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{since}_{until}.md"
            output_path = reports_dir / filename

        output_path.write_text(report_text)
        console.print(f"[green]Report saved to {output_path}[/green]")

    except Exception as e:
        if json_output:
            print_json_error(f"Failed to generate report: {e}", "report_error")
            return
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to generate report")
        sys.exit(1)
