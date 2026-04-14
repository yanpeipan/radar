"""Entity-based report generation pipeline.

Modules:
- filter: SignalFilter (Layer 0)
- template: ReportTemplate, HeadingNode

For CLI entry point functions, import from src.application.report directly
(e.g. from src.application.report import cluster_articles_for_report).
"""

# Re-export CLI entry points from generator module.
from src.application.report.filter import SignalFilter

# Import entry points from sibling module (no circular import since report.py imports from this package)
from src.application.report.generator import (
    cluster_articles_for_report,
)
from src.application.report.models import (
    BuildReportDataChain,
    ReportArticle,
    ReportCluster,
    ReportData,
)
from src.application.report.template import ReportTemplate

__all__ = [
    "SignalFilter",
    "BuildReportDataChain",
    "ReportArticle",
    "ReportCluster",
    "ReportData",
    "ReportTemplate",
    "cluster_articles_for_report",
]
