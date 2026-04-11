"""Data models for entity clustering report pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from src.application.articles import ArticleListItem


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
class ReportArticle(ArticleListItem):
    """Article model for report pipeline, inheriting from ArticleListItem.

    Additional attributes:
        tags: List of entity tags extracted by NER.
        dimensions: List of dimension labels (e.g., release, funding, research).
        similar_articles: Related articles in the same entity cluster.
    """

    tags: list[EntityTag] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    similar_articles: list[ReportArticle] = field(default_factory=list)


@dataclass
class EntityTopic:
    """An entity topic grouping multiple articles.

    Attributes:
        name: Topic name/headline
        summary: One-sentence TLDR summary
        tags: List of entity tags extracted by NER
        children: List of child EntityTopic (sub-topics in same layer)
        articles: Flat list of all articles in this topic
    """

    name: str
    summary: str = field(default_factory=str)
    tags: list[EntityTag] = field(default_factory=list)
    children: list[ReportArticle] = field(default_factory=list)
    articles: list[ReportArticle] = field(default_factory=list)


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
