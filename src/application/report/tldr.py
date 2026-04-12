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
