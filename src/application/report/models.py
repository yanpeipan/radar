"""Data models for entity clustering report pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class Node(ABC):
    """Abstract base class for node entities (e.g., Feed, Group).

    Node entities serve as containers that hold other entities.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Return the unique identifier of this node."""
        ...


class Item(ABC):
    """Abstract base class for item entities (e.g., Article).

    Item entities represent leaf nodes in the hierarchy.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Return the unique identifier of this item."""
        ...

    @property
    @abstractmethod
    def created_at(self) -> str:
        """Return the creation timestamp of this item."""
        ...


@dataclass
class EntityTag:
    """Tag for a named entity extracted from an article.

    Attributes:
        name: Raw entity name (e.g., "Google Gemma 4")
        type: Entity type (ORG, PRODUCT, MODEL, PERSON)
        normalized: Canonical form (e.g., "google_gemma_4")
    """

    name: str
    type: str
    normalized: str


@dataclass
class ArticleEnriched:
    """Article enriched with entity tags and dimension labels.

    Attributes:
        id: Unique article identifier.
        title: Article title.
        link: URL link to the article.
        summary: Short summary or description.
        quality_score: Quality score (0.0-1.0) from signal filter.
        feed_weight: Feed weight (0.0-1.0) for ranking.
        published_at: Publication timestamp.
        feed_id: ID of the feed this article came from.
        entities: List of entity tags extracted by NER.
        dimensions: List of dimension labels (e.g., release, funding, research).
    """

    id: str
    title: str
    link: str
    summary: str
    quality_score: float
    feed_weight: float
    published_at: str
    feed_id: str
    entities: list[EntityTag] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)


@dataclass
class EntityTopic:
    """An entity topic grouping multiple articles.

    Attributes:
        entity_id: Normalized entity identifier (e.g., "google_gemma_4")
        entity_name: Display name (e.g., "Google Gemma 4")
        layer: AI layer classification (AI应用, AI模型, AI基础设施, 芯片, 能源)
        headline: LLM-generated headline summarizing the entity news
        dimensions: Articles grouped by dimension
        articles_count: Total number of articles
        signals: List of signal keywords
        tldr: One-sentence TLDR generated in Layer 3
        quality_weight: Ranking score (quality_score × articles_count)
    """

    entity_id: str
    entity_name: str
    layer: str
    headline: str
    dimensions: dict[str, list[ArticleEnriched]] = field(default_factory=dict)
    articles_count: int = 0
    signals: list[str] = field(default_factory=list)
    tldr: str = ""
    quality_weight: float = 0.0


@dataclass
class ReportData:
    """Complete report data for rendering.

    Attributes:
        tldr_top10: Top 10 entity topics sorted by quality_weight
        by_layer: Entity topics grouped by layer
        by_dimension: Entity topics grouped by dimension
        deep_dive: Large entity topics (articles_count > 50) split by dimension
        date_range: Date range for the report
        target_lang: Target language for the report
    """

    tldr_top10: list[EntityTopic] = field(default_factory=list)
    by_layer: dict[str, list[EntityTopic]] = field(default_factory=dict)
    by_dimension: dict[str, list[EntityTopic]] = field(default_factory=dict)
    deep_dive: list[EntityTopic] = field(default_factory=list)
    date_range: dict[str, str] = field(default_factory=dict)
    target_lang: str = "zh"
