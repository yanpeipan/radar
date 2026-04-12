"""Layer 4: Render — entity report Jinja2 rendering."""

from __future__ import annotations

from .models import ReportData


def group_clusters(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        layer = getattr(t, "layer", "AI应用")
        result.setdefault(layer, []).append(t)
    return result


async def render_report(
    report_data: ReportData,
    template_name: str = "entity",
) -> str:
    """Render entity report using Jinja2."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dirs = [
        Path.home() / ".local" / "share" / "feedship" / "templates",
        Path(__file__).parent.parent.parent.parent / "templates",
    ]
    env = Environment(
        loader=FileSystemLoader([str(d) for d in template_dirs]),
        autoescape=select_autoescape(),
    )
    try:
        template = env.get_template(f"{template_name}.md")
    except Exception:
        raise

    return template.render(report_data=report_data)
