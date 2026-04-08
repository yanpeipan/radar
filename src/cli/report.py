"""Report command — generate structured daily reports from clustered articles."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console

from src.application.report import cluster_articles_for_report, render_report
from src.cli import cli
from src.cli.ui import print_json, print_json_error

logger = logging.getLogger(__name__)
console = Console()


@cli.command("report")
@click.option(
    "--template",
    default="default",
    help="Template name (default: 'default'). Templates stored in ~/.config/feedship/templates/",
)
@click.option("--since", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--until", required=True, help="End date (YYYY-MM-DD)")
@click.option("--output", default=None, help="Save report to file path")
@click.option(
    "--json", "json_output", is_flag=True, help="Machine-readable JSON output"
)
@click.option(
    "--limit",
    default=200,
    help="Max articles to include in report (default: 200)",
)
@click.option(
    "--auto-summarize/--no-auto-summarize",
    default=True,
    help="Automatically summarize unsummarized articles on-demand (default: True)",
)
@click.pass_context
def report(
    ctx: click.Context,
    template: str,
    since: str,
    until: str,
    output: str | None,
    json_output: bool,
    limit: int,
    auto_summarize: bool,
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
            )

        total_articles = sum(len(arts) for arts in data["articles_by_layer"].values())
        summarized_on_demand = data.get("summarized_on_demand", 0)

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

        if summarized_on_demand > 0:
            console.print(
                f"[cyan]Summarized {summarized_on_demand} articles on-demand[/cyan]"
            )

        # Render report
        try:
            report_text = render_report(data, template_name=template)
        except Exception as e:
            if json_output:
                print_json_error(f"Failed to render template: {e}", "template_error")
            console.print(f"[red]Template error: {e}[/red]")
            sys.exit(1)

        if json_output:
            # Build a clean JSON representation
            output_json = {
                "date_range": data["date_range"],
                "total_articles": total_articles,
                "template": template,
                "layers": {},
            }
            for layer, arts in data["articles_by_layer"].items():
                if arts:
                    output_json["layers"][layer] = {
                        "summary": data["layer_summaries"].get(layer, ""),
                        "articles": [
                            {
                                "id": a["id"],
                                "title": a["title"],
                                "link": a["link"],
                                "quality_score": a["quality_score"],
                            }
                            for a in arts
                        ],
                    }
            print_json(output_json)
            return

        # Plain text output
        if output:
            Path(output).write_text(report_text)
            console.print(f"[green]Report saved to {output}[/green]")
        else:
            console.print(report_text)

    except Exception as e:
        if json_output:
            print_json_error(f"Failed to generate report: {e}", "report_error")
            return
        console.print(f"[red]Error: {e}[/red]")
        logger.exception("Failed to generate report")
        sys.exit(1)


# Needed for Path in the CLI
from pathlib import Path
