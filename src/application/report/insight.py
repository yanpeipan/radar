"""Insight Chain — Layer 4: Generate cluster.summary and cluster.children (Topic nodes) for all clusters recursively."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable

if TYPE_CHECKING:
    from src.application.report.models import ReportCluster, ReportData
    from src.llm.output_models import ClusterInsightOutput

logger = logging.getLogger(__name__)


class ClusterProcessChain(Runnable):
    """Async Runnable that processes a single ReportCluster and fills it in-place.

    Returns a fully-populated ReportCluster with title/summary/content set and
    children[] populated from ClusterInsightOutput.topics[].source_indices.

    Args:
        top_n: Number of articles per cluster for insight generation (default: 100).
        target_lang: Target language for insights (default: "zh").
    """

    def __init__(
        self,
        top_n: int = 30,
        target_lang: str = "zh",
    ) -> None:
        self.top_n = top_n
        self.target_lang = target_lang

    def _build_article_titles(self, cluster: ReportCluster) -> tuple[str, list]:
        """Build article_titles for a single cluster with multiple articles.

        Sorts articles by quality_weight descending and takes top_n.
        Returns:
            Tuple of (article_titles_str, sorted_articles_list).
        """
        sorted_articles = sorted(
            cluster.articles,
            key=lambda a: getattr(a, "quality_weight", 0.0) or 0.0,
            reverse=True,
        )[: self.top_n]

        lines = [f"Entity 1 ({cluster.title}):"]
        for j, article in enumerate(sorted_articles, 1):
            content = article.translation or article.title or ""
            lines.append(f"  [{j}] {content}")

        return "\n".join(lines), sorted_articles

    async def ainvoke(self, cluster: ReportCluster, config=None) -> ReportCluster:
        """Process a single cluster and return filled ReportCluster in-place.

        1. Build article_titles string + sorted_articles from cluster.articles
        2. Call get_cluster_insight_chain() -> ClusterInsightOutput
        3. Fill cluster.title/summary/content from output
        4. For each topic in output.topics:
           - Create child ReportCluster with topic.title/summary/content
           - Map source_indices to articles via sorted_articles[idx-1]
           - Append to cluster.children
        5. Return cluster (in-place filled)
        """
        from src.application.report.models import ReportCluster as RC
        from src.llm.chains import get_cluster_insight_chain

        article_titles, sorted_articles = self._build_article_titles(cluster)
        chain = get_cluster_insight_chain()
        output: ClusterInsightOutput = await chain.ainvoke(
            {
                "article_titles": article_titles,
                "target_lang": self.target_lang,
                "top_n": self.top_n,
            }
        )

        # Fill cluster fields from flat output
        cluster.title = output.title
        cluster.summary = output.summary
        cluster.content = output.content

        # Build children from topics with source_indices -> articles mapping
        cluster.children = []
        for topic in output.topics:
            child = RC(
                title=topic.title,
                summary=topic.summary,
                content=topic.content,
                children=[],
                articles=[],
            )
            child.articles = [sorted_articles[idx - 1] for idx in topic.source_indices]
            cluster.children.append(child)

        return cluster

    def invoke(self, cluster: ReportCluster, config=None) -> ReportCluster:
        """Sync wrapper using asyncio.run() pattern."""
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.ainvoke(cluster, config))
        except RuntimeError:
            return asyncio.run(self.ainvoke(cluster, config))


class InsightChain(Runnable):
    """Async Runnable that generates cluster.summary and cluster.children for all clusters.

    Delegates per-cluster processing to ClusterProcessChain for concurrent execution.
    All clusters with articles go through the same insight processing (no size distinction).

    Args:
        top_n: Number of articles per cluster for insight generation (default: 100).
            Each cluster passes at most top_n articles (sorted by quality_weight) to the LLM.
        target_lang: Target language for insights (default: "zh").
        max_concurrency: Maximum concurrent LLM calls (default: 5).
    """

    def __init__(
        self,
        top_n: int = 30,
        target_lang: str = "zh",
        max_concurrency: int = 1,
    ) -> None:
        self.top_n = top_n
        self.target_lang = target_lang
        self.max_concurrency = max_concurrency

    async def ainvoke(self, input: ReportData, config=None) -> ReportData:
        """Generate cluster.summary and cluster.children for all clusters with articles.

        1. Collect all clusters recursively
        2. Filter clusters with articles
        3. Delegate each cluster to ClusterProcessChain concurrently
           (ClusterProcessChain now fills cluster in-place)
        4. Return input
        """
        # Step 1: collect all clusters
        all_clusters = input.collect_all_clusters()

        # Step 2: filter clusters with articles
        clusters_with_articles = [c for c in all_clusters if c.articles]

        if not clusters_with_articles:
            return input

        # Step 3: delegate to ClusterProcessChain with concurrency control
        chain = ClusterProcessChain(top_n=self.top_n, target_lang=self.target_lang)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def process_cluster(cluster: ReportCluster) -> None:
            async with semaphore:
                try:
                    await chain.ainvoke(cluster)
                except Exception as e:
                    logger.warning("ClusterProcessChain failed: %s", e)

        await asyncio.gather(
            *[process_cluster(c) for c in clusters_with_articles],
            return_exceptions=True,
        )

        return input

    def invoke(self, input: ReportData, config=None) -> ReportData:
        """Sync wrapper using asyncio.run() pattern."""
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.ainvoke(input, config))
        except RuntimeError:
            return asyncio.run(self.ainvoke(input, config))

    async def abatch(self, inputs: list[ReportData], config=None) -> list[ReportData]:
        """Process multiple ReportData inputs."""
        return [await self.ainvoke(inp, config) for inp in inputs]

    def batch(self, inputs: list[ReportData], config=None) -> list[ReportData]:
        """Sync wrapper for abatch."""
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(self.abatch(inputs))
        except RuntimeError:
            return asyncio.run(self.abatch(inputs))
