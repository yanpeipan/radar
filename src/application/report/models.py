"""Data models for entity clustering report pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

from src.application.articles import ArticleListItem
from src.application.report.template import HeadingNode


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
    """Article model for report pipeline, inheriting from ArticleListItem."""
    # tags, dimensions, translation inherited from ArticleListItem
    similar_articles: list[ReportArticle] = field(default_factory=list)

    @classmethod
    def from_article(cls, item: ArticleListItem, cluster_name: str) -> ReportArticle:
        """Convert an ArticleListItem to ReportArticle."""
        return cls(**asdict(item))


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
    children: list[ReportCluster] = field(default_factory=list)
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
        # Find existing cluster via recursive search, or create at top level
        cluster = self.get_cluster(cluster_name)
        if cluster is None:
            if cluster_name not in self.clusters:
                self.clusters[cluster_name] = []
            cluster = ReportCluster(name=cluster_name)
            self.clusters[cluster_name].append(cluster)

        cluster.children.append(ReportArticle.from_article(item, cluster_name))

    def get_cluster(self, cluster_name: str) -> ReportCluster | None:
        """Get the first cluster with the given name, searching recursively.

        Args:
            cluster_name: Name of the cluster to find

        Returns:
            The first matching ReportCluster, or None if not found
        """
        for cluster_list in self.clusters.values():
            result = self._find_cluster_in_list(cluster_list, cluster_name)
            if result is not None:
                return result
        return None

    def _find_cluster_in_list(
        self, clusters: list[ReportCluster], name: str
    ) -> ReportCluster | None:
        """Recursively find a cluster by name in a list of clusters."""
        for cluster in clusters:
            if cluster.name == name:
                return cluster
            # Search in children
            if cluster.children:
                result = self._find_cluster_in_list(cluster.children, name)
                if result is not None:
                    return result
        return None
