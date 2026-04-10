"""Entity-based report generation pipeline.

Modules:
- filter: SignalFilter (Layer 0)
- ner: NERExtractor (Layer 1)
- entity_cluster: EntityClusterer (Layer 2)
- tldr: TLDRGenerator (Layer 3)
- render: render_entity_report (Layer 4)

For CLI entry point functions, import from src.application.report directly
(e.g. from src.application.report import cluster_articles_for_report).
"""

# Re-export CLI entry points from report.py (the module, not the package).
# Use importlib to avoid circular import since report.py imports from this package.
import importlib.machinery
import os as _os

from src.application.report.entity_cluster import EntityClusterer
from src.application.report.filter import SignalFilter
from src.application.report.models import (
    ArticleEnriched,
    EntityTag,
    EntityTopic,
    ReportData,
)
from src.application.report.ner import NERExtractor
from src.application.report.render import (
    dim_zh,
    group_by_dimension,
    group_by_layer,
    render_entity_inline,
    render_entity_report,
)
from src.application.report.tldr import TLDRGenerator

_report_py = _os.path.join(
    _os.path.dirname(_os.path.dirname(__file__)), "report_generation.py"
)
_loader = importlib.machinery.SourceFileLoader(
    "src.application.report.report", _report_py
)
_report_mod = _loader.load_module()

cluster_articles_for_report = _report_mod.cluster_articles_for_report
render_report = _report_mod.render_report
LAYER_KEYS = _report_mod.LAYER_KEYS

__all__ = [
    "SignalFilter",
    "NERExtractor",
    "EntityClusterer",
    "TLDRGenerator",
    "render_entity_report",
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
