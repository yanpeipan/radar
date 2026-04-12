"""Entity-based report generation pipeline.

Modules:
- filter: SignalFilter (Layer 0)
- tldr: TLDRGenerator (Layer 2)
- render: render_report (Layer 3)

For CLI entry point functions, import from src.application.report directly
(e.g. from src.application.report import cluster_articles_for_report).
"""

# Re-export CLI entry points from report_generation module.
from src.application.report.filter import SignalFilter
from src.application.report.models import (
    EntityTag,
    ReportArticle,
    ReportCluster,
    ReportData,
)
from src.application.report.render import (
    group_clusters,
    render_report,
)

# Import entry points from sibling module (no circular import since report.py imports from this package)
from src.application.report.report_generation import (
    cluster_articles_for_report,
)
from src.application.report.tldr import TLDRGenerator

__all__ = [
    "SignalFilter",
    "TLDRGenerator",
    "render_report",
    "group_clusters",
    "ReportArticle",
    "EntityTag",
    "ReportCluster",
    "ReportData",
    "cluster_articles_for_report",
]
