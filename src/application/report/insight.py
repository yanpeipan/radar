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
        lines = [f"Entity 1 ({cluster.name}):"]
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
        all_clusters = self._collect_all_clusters(input.clusters)

        # Step 2: filter clusters with articles
        clusters_with_articles = [c for c in all_clusters if c.articles]

        if not clusters_with_articles:
            return input

        # Step 3: separate by article count
        rich_clusters = [c for c in clusters_with_articles if len(c.articles) >= 2]
        simple_clusters = [
            c
            for c in clusters_with_articles
            if len(c.articles) < 2 and len(c.articles) > 0
        ]

        # Step 4a: process rich clusters (>= 2 articles) with full insight chain
        if rich_clusters:
            chain = get_insight_chain()
            inputs = []
            for c in rich_clusters:
                article_titles, _ = self._build_article_titles(c)
                inputs.append(
                    {
                        "article_titles": article_titles,
                        "target_lang": self.target_lang,
                        "top_n": self.top_n,
                    }
                )

            results = await chain.abatch(
                inputs, return_exceptions=True, max_concurrency=self.max_concurrency
            )

            # Map results back to clusters
            for cluster, result in zip(rich_clusters, results, strict=True):
                if isinstance(result, Exception):
                    logger.warning("InsightChain cluster failed: %s", result)
                elif result and hasattr(result, "topics"):
                    # Normalize topic_ids and assign to cluster.children
                    cluster.children = []
                    for topic in result.topics:
                        # Normalize topic_id format: "Topic 1" -> "Topic_01"
                        topic_id = topic.topic_id.replace(" ", "_")
                        if not topic_id.startswith("Topic_"):
                            topic_id = f"Topic_{topic_id}"
                        normalized_topic = type(topic)(
                            topic_id=topic_id,
                            title=topic.title,
                            summary=topic.summary,
                            insights=topic.insights,
                        )
                        cluster.children.append(normalized_topic)
                    # cluster.summary is set below from the first topic's summary or cluster-level summary
                    if result.topics:
                        cluster.summary = result.topics[0].summary

        # Step 4b: process simple clusters (< 2 articles) with simple summary only
        if simple_clusters:
            from src.llm.chains import get_simple_summary_chain

            for cluster in simple_clusters:
                article_titles, _ = self._build_article_titles(cluster)
                try:
                    chain = get_simple_summary_chain()
                    result = await chain.ainvoke(
                        {
                            "article_titles": article_titles,
                            "target_lang": self.target_lang,
                        }
                    )
                    cluster.summary = (
                        result.strip() if isinstance(result, str) else str(result)
                    )
                except Exception as e:
                    logger.warning(
                        "Simple summary failed for cluster %s: %s", cluster.name, e
                    )
                    # Fallback: use article title as summary
                    if cluster.articles:
                        cluster.summary = (
                            cluster.articles[0].translation
                            or cluster.articles[0].title
                            or ""
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
