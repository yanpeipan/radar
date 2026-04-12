"""Layer 4: Render — entity report Jinja2 rendering."""

from __future__ import annotations

from .models import ReportData
from .template import ReportTemplate


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
    """Backward-compatible wrapper using default ReportTemplate."""
    template = ReportTemplate()
    return await template.render(report_data, template_name)
