"""TLDR Chain — Layer 4: Generate TLDR summaries for all clusters recursively."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable

if TYPE_CHECKING:
    from src.application.report.models import ReportCluster, ReportData

logger = logging.getLogger(__name__)


class TLDRChain(Runnable):
    """Async Runnable that generates TLDR summaries for all clusters.

    Each cluster is processed individually with its top_n articles.
    Concurrency is controlled via max_concurrency semaphore.

    Args:
        top_n: Number of articles per cluster for TLDR generation (default: 100).
            Each cluster passes at most top_n articles (sorted by quality_weight) to the LLM.
        target_lang: Target language for TLDR summaries (default: "zh").
        max_concurrency: Maximum concurrent LLM calls (default: 5).
    """

    def __init__(
        self,
        top_n: int = 100,
        target_lang: str = "zh",
        max_concurrency: int = 5,
    ) -> None:
        self.top_n = top_n
        self.target_lang = target_lang
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

    def _build_article_titles(self, cluster: ReportCluster) -> str:
        """Build article_titles for a single cluster with multiple articles.

        Sorts articles by quality_weight descending and takes top_n.
        Format:
        "Entity 1 ({name}):
          [1] article_title_or_translation
          [2] article_title_or_translation
          ..."
        """
        # Sort articles by quality_weight descending and take top_n
        sorted_articles = sorted(
            cluster.articles,
            key=lambda a: getattr(a, "quality_weight", 0.0) or 0.0,
            reverse=True,
        )[: self.top_n]

        # Build multi-article block
        lines = [f"Entity 1 ({cluster.name}):"]
        for j, article in enumerate(sorted_articles, 1):
            content = article.translation or article.title or ""
            lines.append(f"  [{j}] {content}")

        return "\n".join(lines)

    async def ainvoke(self, input: ReportData, config=None) -> ReportData:
        """Generate TLDR summaries for all clusters with articles.

        1. Collect all clusters recursively
        2. Filter clusters with articles
        3. Batch call get_tldr_chain with max_concurrency control
        """
        from src.llm.chains import get_tldr_chain

        # Step 1: collect all clusters
        all_clusters = self._collect_all_clusters(input.clusters)

        # Step 2: filter clusters with articles
        clusters_with_articles = [c for c in all_clusters if c.articles]

        if not clusters_with_articles:
            return input

        # Step 3: batch call LLM with concurrency control
        chain = get_tldr_chain()
        inputs = [
            {
                "article_titles": self._build_article_titles(c),
                "target_lang": self.target_lang,
                "top_n": self.top_n,
            }
            for c in clusters_with_articles
        ]
        results = await chain.abatch(
            inputs, return_exceptions=True, max_concurrency=self.max_concurrency
        )

        # Map results back to clusters
        for cluster, result in zip(clusters_with_articles, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("TLDR cluster failed: %s", result)
            elif result:
                # Handle structured output: result is TLDRItems with .items list
                items = result.items if hasattr(result, "items") else result
                if items:
                    cluster.summary = items[0].tldr

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
            return loop.run_until_complete(self.abatch(inputs))
        finally:
            loop.close()
