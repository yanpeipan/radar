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
    translation: str = ""


@dataclass
class ReportCluster:
    """An entity topic grouping multiple articles.

    Attributes:
        name: Topic name/headline
        summary: One-sentence TLDR summary
        tags: List of entity tags extracted by NER
        children: List of child ReportCluster (sub-topics in same layer)
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
        clusters: Entity topics grouped by layer
        date_range: Date range for the report
        target_lang: Target language for the report
    """

    clusters: dict[str, list[ReportCluster]] = field(default_factory=dict)
    date_range: dict[str, str] = field(default_factory=dict)
    target_lang: str = "zh"
    heading_tree: HeadingNode | None = field(default=None)

    @property
    def total_articles(self) -> int:
        """Total number of articles across all clusters."""
        return sum(
            len(cluster.children)
            for cluster_list in self.clusters.values()
            for cluster in cluster_list
        )

    def add_article(self, cluster_name: str, item: ArticleListItem) -> None:
        """Add an article to a cluster, creating the cluster if needed.

        Args:
            cluster_name: Key in self.clusters (e.g., "AI应用")
            item: ArticleListItem (should have .tags and .translation from enrichment)
        """
        # Get or create cluster list
        if cluster_name not in self.clusters:
            self.clusters[cluster_name] = []

        clusters = self.clusters[cluster_name]

        # Use existing cluster or create new one with this article as first child
        if not clusters:
            cluster = ReportCluster(name=cluster_name)
            clusters.append(cluster)
        else:
            cluster = clusters[0]

        # Convert ArticleListItem to ReportArticle
        art = ReportArticle(
            id=item.id or "",
            feed_id=item.feed_id or "",
            feed_name=item.feed_name or "",
            title=item.title or "",
            link=item.link or "",
            guid=item.guid or "",
            published_at=item.published_at or "",
            description=item.description or "",
            tags=item.tags,
            dimensions=[cluster_name],
            translation=item.translation or "",
        )
        cluster.children.append(art)
