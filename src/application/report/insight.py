"""Insight Chain — Layer 4: Generate cluster.summary and cluster.children (Topic nodes) for all clusters recursively."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable

if TYPE_CHECKING:
    from src.application.report.models import ReportCluster, ReportData

logger = logging.getLogger(__name__)


class InsightChain(Runnable):
    """Async Runnable that generates cluster.summary and cluster.children for all clusters.

    Each cluster is processed individually with its top_n articles.
    For clusters with >= 2 articles: generates cluster.summary (one-sentence TLDR) AND
    cluster.children (Topic nodes with Insights).
    For clusters with < 2 articles: only generates cluster.summary.
    Concurrency is controlled via max_concurrency semaphore.

    Args:
        top_n: Number of articles per cluster for insight generation (default: 100).
            Each cluster passes at most top_n articles (sorted by quality_weight) to the LLM.
        target_lang: Target language for insights (default: "zh").
        max_concurrency: Maximum concurrent LLM calls (default: 5).
    """

    def __init__(
        self,
        top_n: int = 100,
        target_lang: str = "zh",
        max_concurrency: int = 1,
    ) -> None:
        self.top_n = top_n
        self.target_lang = target_lang
        self.max_concurrency = max_concurrency

    def _build_article_titles(self, cluster: ReportCluster) -> tuple[str, list]:
        """Build article_titles for a single cluster with multiple articles.

        Sorts articles by quality_weight descending and takes top_n.
        Format:
        "Entity 1 ({name}):
          [1] article_title_or_translation
          [2] article_title_or_translation
          ..."

        Returns:
            Tuple of (article_titles_str, sorted_articles_list) where indices in the
            string correspond to 1-based positions in the returned articles list.
        """
        # Sort articles by quality_weight descending and take top_n
        sorted_articles = sorted(
            cluster.articles,
            key=lambda a: getattr(a, "quality_weight", 0.0) or 0.0,
            reverse=True,
        )[: self.top_n]

        # Build multi-article block
        lines = [f"Entity 1 ({cluster.title}):"]
        for j, article in enumerate(sorted_articles, 1):
            content = article.translation or article.title or ""
            lines.append(f"  [{j}] {content}")

        return "\n".join(lines), sorted_articles

    async def ainvoke(self, input: ReportData, config=None) -> ReportData:
        """Generate cluster.summary and cluster.children for all clusters with articles.

        1. Collect all clusters recursively
        2. Filter clusters with articles
        3. Separate clusters by article count (>= 2 vs < 2)
        4. Batch call get_insight_chain for clusters with >= 2 articles
        5. Map results back to clusters (cluster.summary + cluster.children)
        """
        from src.llm.chains import get_insight_chain

        # Step 1: collect all clusters
        all_clusters = input.collect_all_clusters()

        # Step 2: filter clusters with articles
        clusters_with_articles = [c for c in all_clusters if c.articles]

        if not clusters_with_articles:
            return input

        # Step 4a: process rich clusters (>= 2 articles) with full insight chain
        # Phase 2: Each cluster independently generates children from its own articles
        if clusters_with_articles:
            chain = get_insight_chain()
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def process_rich_cluster(cluster: ReportCluster) -> None:
                async with semaphore:
                    article_titles, _ = self._build_article_titles(cluster)
                    try:
                        result = await chain.ainvoke(
                            {
                                "article_titles": article_titles,
                                "target_lang": self.target_lang,
                                "top_n": self.top_n,
                            }
                        )
                        if result and hasattr(result, "topics"):
                            # Assign topic_id and convert to ReportCluster for cluster.children
                            cluster.children = []
                            for i, topic in enumerate(result.topics, start=1):
                                topic_id = f"Topic_{i:02d}"
                                from src.application.report.models import ReportCluster

                                rc = ReportCluster(
                                    title=topic_id,
                                    summary=topic.summary,
                                    children=[],
                                    articles=[],
                                )
                                cluster.children.append(rc)
                            if result.topics:
                                cluster.summary = result.topics[0].summary
                    except Exception as e:
                        logger.warning("InsightChain cluster failed: %s", e)

            await asyncio.gather(
                *[process_rich_cluster(c) for c in clusters_with_articles],
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
