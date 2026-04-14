"""Data models for entity clustering report pipeline."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable

from src.application.articles import ArticleListItem

if TYPE_CHECKING:
    from src.application.report.template import HeadingNode

logger = logging.getLogger(__name__)


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
class ReportArticle(ArticleListItem):
    """Article model for report pipeline, inheriting from ArticleListItem."""

    # tags, dimensions, translation inherited from ArticleListItem
    similar_articles: list[ReportArticle] = field(default_factory=list)

    @classmethod
    def from_article(
        cls,
        item: ArticleListItem,
        similar_articles: list[ReportArticle] | None = None,
    ) -> ReportArticle:
        """Convert an ArticleListItem to ReportArticle."""
        kwargs = asdict(item)
        kwargs["similar_articles"] = (
            similar_articles if similar_articles is not None else []
        )
        return cls(**kwargs)


@dataclass
class ReportCluster:
    """An entity topic grouping multiple articles.

    Attributes:
        title: Topic name/headline
        content: Long-form content (distinct from summary's short-form)
        summary: One-sentence TLDR summary
        tags: List of entity tags extracted by NER
        children: List of child ReportCluster (sub-topics in same layer)
        articles: Flat list of all articles in this topic
    """

    title: str
    content: str = field(default=str)
    summary: str = field(default_factory=str)
    tags: list[str] = field(default_factory=list)
    children: list[ReportCluster] = field(default_factory=list)
    articles: list[ReportArticle] = field(default_factory=list)


@dataclass
class ReportData:
    """Complete report data for rendering.

    Attributes:
        cluster: Root ReportCluster containing all topic children
        date_range: Date range for the report
        target_lang: Target language for the report
    """

    cluster: ReportCluster = field(default_factory=lambda: ReportCluster(title=""))
    date_range: dict[str, str] = field(default_factory=dict)
    target_lang: str = "zh"
    heading_tree: HeadingNode | None = field(default=None)

    @property
    def total_articles(self) -> int:
        """Total number of articles across all clusters (recursive)."""

        def count(c: ReportCluster) -> int:
            return len(c.articles) + sum(count(child) for child in c.children)

        return count(self.cluster)

    def add_article(self, cluster_name: str, item: ArticleListItem) -> None:
        """Add an article to a cluster in cluster.children, creating if needed.

        Args:
            cluster_name: Key in cluster.children (e.g., "AI应用")
            item: ArticleListItem (should have .tags and .translation from enrichment)
        """
        cluster = self._find_cluster_in_children(self.cluster.children, cluster_name)
        if cluster is None:
            cluster = ReportCluster(title=cluster_name)
            self.cluster.children.append(cluster)
        cluster.articles.append(ReportArticle.from_article(item))

    def add_articles(
        self, items: list[ArticleListItem], get_tag: Callable[[ArticleListItem], str]
    ) -> None:
        """Add multiple articles to clusters, calling add_article for each.

        Args:
            items: List of ArticleListItem to add
            get_tag: Function to extract cluster name from each item
        """
        for item in items:
            self.add_article(get_tag(item), item)

    def build(self, heading_tree: HeadingNode | None) -> None:
        """Match clusters to heading_tree nodes by title, populate cluster.children."""
        # Skip rebuild when:
        # 1. heading_tree is None (no template)
        # 2. heading_tree has no children (empty template)
        # 3. heading_tree children are Jinja2 placeholders (dynamic template iterating over cluster.children)
        if heading_tree is None or not heading_tree.children:
            return
        # Check if children are Jinja2 placeholders (dynamic content, not static headings)
        if any(
            "{{" in node.title or "{%" in node.title for node in heading_tree.children
        ):
            return  # Skip rebuild - template uses dynamic cluster.children iteration
        self.cluster.children = []
        for node in heading_tree.children:
            matched = self.get_cluster(node.title)
            if matched is None:
                matched = ReportCluster(title=node.title, children=[], articles=[])
            self.cluster.children.append(matched)

    def get_cluster(self, cluster_name: str) -> ReportCluster | None:
        """Get the first cluster with the given name, searching recursively."""
        return self._find_cluster_in_children(self.cluster.children, cluster_name)

    def _find_cluster_in_children(
        self, children: list[ReportCluster], name: str
    ) -> ReportCluster | None:
        """Find a cluster by name in a list of children recursively."""
        for c in children:
            if c.title == name:
                return c
            result = self._find_cluster_in_children(c.children, name)
            if result is not None:
                return result
        return None


# ---------------------------------------------------------------------------
# Layer 3: BuildReportDataChain — wraps ReportData.add_articles + build
# ---------------------------------------------------------------------------


class BuildReportDataChain(Runnable):
    """Async Runnable that wraps ReportData.add_articles() + build().

    Input: list[ArticleListItem] (heading_tree passed via constructor)
    Output: ReportData with articles added and clusters built from heading_tree
    """

    def __init__(
        self,
        heading_tree: HeadingNode | None = None,
        target_lang: str = "zh",
        fallback_tag: str = "其他",
    ) -> None:
        self.heading_tree = heading_tree
        self.target_lang = target_lang
        self.fallback_tag = fallback_tag

    async def ainvoke(
        self,
        input: list[ArticleListItem],
        config=None,
    ) -> ReportData:
        """Add articles to ReportData and build clusters from heading_tree."""
        items = input
        report_data = ReportData(
            cluster=ReportCluster(title=""),
            date_range={},
            target_lang=self.target_lang,
            heading_tree=self.heading_tree,
        )
        report_data.add_articles(
            items, lambda a: a.tags[0] if a.tags else self.fallback_tag
        )
        report_data.build(self.heading_tree)
        return report_data

    def invoke(
        self,
        input: list[ArticleListItem],
        config=None,
    ) -> ReportData:
        """Sync wrapper using asyncio.run() pattern."""
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.ainvoke(input, config))
        except RuntimeError:
            return asyncio.run(self.ainvoke(input, config))

    async def abatch(
        self,
        inputs: list[list[ArticleListItem]],
        config=None,
    ) -> list[ReportData]:
        """Process multiple article lists."""
        return [await self.ainvoke(inp, config) for inp in inputs]

    def batch(
        self,
        inputs: list[list[ArticleListItem]],
        config=None,
    ) -> list[ReportData]:
        """Sync wrapper for abatch."""
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.abatch(inputs, config))
        except RuntimeError:
            return asyncio.run(self.abatch(inputs, config))
