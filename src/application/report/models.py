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
        name: Topic name/headline
        summary: One-sentence TLDR summary
        tags: List of entity tags extracted by NER
        children: List of child ReportCluster (sub-topics in same layer)
        articles: Flat list of all articles in this topic
    """

    name: str
    summary: str = field(default_factory=str)
    tags: list[str] = field(default_factory=list)
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
            len(cluster.articles)
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
        """Match clusters to heading_tree nodes by title.

        Each heading title is matched against existing clusters by name.
        If a heading has no matching cluster, create an empty one.
        """
        if heading_tree is None:
            return
        clusters: dict[str, list[ReportCluster]] = {}
        for node in heading_tree.children:
            matched = self.get_cluster(node.title)
            if matched is None:
                matched = ReportCluster(name=node.title, children=[], articles=[])
            clusters.setdefault(node.title, []).append(matched)
        self.clusters = clusters

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


# ---------------------------------------------------------------------------
# Layer 3: BuildReportDataChain — wraps ReportData.add_articles + build
# ---------------------------------------------------------------------------


class BuildReportDataChain(Runnable):
    """Async Runnable that wraps ReportData.add_articles() + build().

    Input: tuple of (list[ArticleListItem], HeadingNode | None)
    Output: ReportData with articles added and clusters built from heading_tree
    """

    def __init__(self, target_lang: str = "zh") -> None:
        self.target_lang = target_lang

    async def ainvoke(
        self,
        input: tuple[list[ArticleListItem], HeadingNode | None],
        config=None,
    ) -> ReportData:
        """Add articles to ReportData and build clusters from heading_tree."""
        items, heading_tree = input
        report_data = ReportData(
            clusters={},
            date_range={},
            target_lang=self.target_lang,
            heading_tree=heading_tree,
        )
        report_data.add_articles(items, lambda a: a.tags[0] if a.tags else "unknown")
        report_data.build(heading_tree)
        return report_data

    def invoke(
        self,
        input: tuple[list[ArticleListItem], HeadingNode | None],
        config=None,
    ) -> ReportData:
        """Sync wrapper using new_event_loop pattern."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.ainvoke(input, config))
        finally:
            loop.close()

    async def abatch(
        self,
        inputs: list[tuple[list[ArticleListItem], HeadingNode | None]],
        config=None,
    ) -> list[ReportData]:
        """Process multiple (items, heading_tree) inputs."""
        return [await self.ainvoke(inp, config) for inp in inputs]

    def batch(
        self,
        inputs: list[tuple[list[ArticleListItem], HeadingNode | None]],
        config=None,
    ) -> list[ReportData]:
        """Sync wrapper for abatch."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.abatch(inputs, config))
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Layer 4: TLDRChain — recursively generates TLDR for all clusters
# ---------------------------------------------------------------------------


class TLDRChain(Runnable):
    """Async Runnable that generates TLDR summaries for all clusters recursively.

    Traverses all clusters (including cluster.children), filters those with articles,
    batches calls to get_tldr_chain, and writes cluster.summary.
    """

    def __init__(
        self,
        top_n: int = 100,
        target_lang: str = "zh",
        batch_size: int = 20,
        max_concurrency: int = 5,
    ) -> None:
        self.top_n = top_n
        self.target_lang = target_lang
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency

    def _collect_all_clusters(
        self, clusters: dict[str, list[ReportCluster]]
    ) -> list[ReportCluster]:
        """Recursively flatten all clusters including children."""
        all_clusters: list[ReportCluster] = []
        for cluster_list in clusters.values():
            all_clusters.extend(self._flatten_clusters(cluster_list))
        return all_clusters

    def _flatten_clusters(self, clusters: list[ReportCluster]) -> list[ReportCluster]:
        """Flatten a list of clusters recursively."""
        result: list[ReportCluster] = []
        for cluster in clusters:
            result.append(cluster)
            if cluster.children:
                result.extend(self._flatten_clusters(cluster.children))
        return result

    def _build_topics_block(self, clusters: list[ReportCluster]) -> str:
        """Build topics_block string for get_tldr_chain prompt.

        Format per cluster:
        "Entity {i+1} ({name}): {first_article_translation or title}"
        """
        lines: list[str] = []
        for i, cluster in enumerate(clusters):
            first_article = cluster.articles[0] if cluster.articles else None
            content = ""
            if first_article:
                content = first_article.translation or first_article.title or ""
            lines.append(f"Entity {i + 1} ({cluster.name}): {content}")
        return "\n".join(lines)

    async def ainvoke(self, input: ReportData, config=None) -> ReportData:
        """Generate TLDR summaries for all clusters with articles.

        1. Collect all clusters recursively
        2. Filter clusters with articles
        3. Sort by quality_weight descending and take top_n
        4. Batch clusters, call get_tldr_chain for each batch
        5. Map TLDRItem.entity_id -> cluster.name, write TLDRItem.tldr -> cluster.summary
        """
        from src.llm.chains import get_tldr_chain

        # Step 1: collect all clusters
        all_clusters = self._collect_all_clusters(input.clusters)

        # Step 2: filter clusters with articles
        clusters_with_articles = [c for c in all_clusters if c.articles]

        # Step 3: sort by quality_weight descending and take top_n
        # quality_weight may not exist on all articles; default to 0
        def cluster_quality(c: ReportCluster) -> float:
            weights = [getattr(a, "quality_weight", 0.0) or 0.0 for a in c.articles]
            return max(weights) if weights else 0.0

        sorted_clusters = sorted(
            clusters_with_articles, key=cluster_quality, reverse=True
        )[: self.top_n]

        if not sorted_clusters:
            return input

        # Step 4: batch clusters and call get_tldr_chain
        batches: list[list[ReportCluster]] = [
            sorted_clusters[i : i + self.batch_size]
            for i in range(0, len(sorted_clusters), self.batch_size)
        ]
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def process_batch(batch: list[ReportCluster]) -> list[ReportCluster]:
            async with semaphore:
                try:
                    topics_block = self._build_topics_block(batch)
                    chain = get_tldr_chain()
                    output = await chain.ainvoke(
                        {"topics_block": topics_block, "target_lang": self.target_lang}
                    )
                    # Step 5: map TLDRItem back to clusters
                    tldr_by_name = {item.entity_id: item.tldr for item in output}
                    for cluster in batch:
                        if cluster.name in tldr_by_name:
                            cluster.summary = tldr_by_name[cluster.name]
                    return batch
                except Exception as e:
                    logger.warning("TLDR batch failed: %s", e)
                    return batch

        await asyncio.gather(*[process_batch(b) for b in batches])

        return input

    def invoke(self, input: ReportData, config=None) -> ReportData:
        """Sync wrapper using new_event_loop pattern."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.ainvoke(input, config))
        finally:
            loop.close()

    async def abatch(self, inputs: list[ReportData], config=None) -> list[ReportData]:
        """Process multiple ReportData inputs."""
        return [await self.ainvoke(inp, config) for inp in inputs]

    def batch(self, inputs: list[ReportData], config=None) -> list[ReportData]:
        """Sync wrapper for abatch."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.abatch(inputs, config))
        finally:
            loop.close()
