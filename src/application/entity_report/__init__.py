"""AI report generation - entity clustering pipeline.

Exports:
    SignalFilter: Layer 0 - exact dedup + quality/feed_weight gate.
    NERExtractor: Layer 1 - batch LLM NER extraction + entity normalization.
    EntityClusterer: Layer 2 - group by entity, dimension classify, headline LLM.
    TLDRGenerator: Layer 3 - top-10 TLDR summary via single LLM call.
    ReportData: Dataclass models for the report pipeline.
"""

from .models import (
    ArticleEnriched,
    EntityTag,
    EntityTopic,
    ReportData,
)
from .filter import SignalFilter
from .ner import NERExtractor
from .entity_cluster import EntityClusterer
from .tldr import TLDRGenerator

__all__ = [
    "ArticleEnriched",
    "EntityTag",
    "EntityTopic",
    "ReportData",
    "SignalFilter",
    "NERExtractor",
    "EntityClusterer",
    "TLDRGenerator",
]
