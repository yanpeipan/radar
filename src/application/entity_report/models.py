"""Data models for the report entity clustering pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EntityTag:
    """A named entity extracted from an article."""

    name: str
    normalized_id: str
    type: str  # e.g. "PERSON", "ORG", "PRODUCT", "TECH"


@dataclass
class ArticleEnriched:
    """Article enriched with extracted entities and metadata."""

    id: int
    title: str
    link: str
    summary: str
    quality_score: float
    feed_weight: float
    published_at: Optional[datetime]
    feed_id: str
    entities: list[EntityTag] = field(default_factory=list)
    layer: str = "AI应用"  # AI five-layer cake category


@dataclass
class EntityTopic:
    """A cluster of articles grouped by a common entity."""

    entity: EntityTag
    articles: list[ArticleEnriched]
    dimension: str = "release"  # release | funding | research | ecosystem | policy
    headline: str = ""
    signals: list[str] = field(default_factory=list)
    quality_weight: float = 0.0


@dataclass
class ReportData:
    """Top-level report data container."""

    by_layer: list[dict] = field(default_factory=list)
    by_dimension: list[dict] = field(default_factory=list)
    deep_dive: list[EntityTopic] = field(default_factory=list)
    tldr_top10: list[str] = field(default_factory=list)
    date_range: dict = field(default_factory=dict)
