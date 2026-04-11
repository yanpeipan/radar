"""Entity-based report generation pipeline.

Modules:
- filter: SignalFilter (Layer 0)
- entity_cluster: EntityClusterer (Layer 1)
- tldr: TLDRGenerator (Layer 2)
- render: render_report (Layer 3)

For CLI entry point functions, import from src.application.report directly
(e.g. from src.application.report import cluster_articles_for_report).
"""

# Re-export CLI entry points from report_generation module.
from src.application.report.filter import SignalFilter
from src.application.report.models import (
    ArticleEnriched,
    EntityTag,
    EntityTopic,
    ReportData,
)
from src.application.report.render import (
    dim_zh,
    group_by_dimension,
    group_by_layer,
    render_entity_inline,
    render_report,
)

# Import entry points from sibling module (no circular import since report.py imports from this package)
from src.application.report.report_generation import (
    LAYER_KEYS,
    cluster_articles_for_report,
    render_report,
)
from src.application.report.tldr import TLDRGenerator

__all__ = [
    "SignalFilter",
    "TLDRGenerator",
    "render_report",
    "render_entity_inline",
    "group_by_layer",
    "group_by_dimension",
    "dim_zh",
    "ArticleEnriched",
    "EntityTag",
    "EntityTopic",
    "ReportData",
    "cluster_articles_for_report",
    "render_report",
    "LAYER_KEYS",
]
