"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .template import HeadingNode

from src.application.articles import ArticleListItem
from src.application.report.models import ReportArticle, ReportCluster, ReportData
from src.storage import list_articles

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v2 report helpers — topic clustering
# ---------------------------------------------------------------------------


async def _entity_report_async(
    pre_fetched_articles: list[ArticleListItem],
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
    heading_tree: HeadingNode | None = None,
) -> ReportData:
    """New entity-based report pipeline (5 layers).

    Layer 0: Signal Filter (rules)
    Layer 1: Enrich (pass-through)
    Layer 2: Entity Clustering (LLM)
    Layer 3: TLDR Generation (1 LLM call)
    Layer 4: Render (Jinja2)
    """
    import logging

    logger = logging.getLogger(__name__)

    from src.application.report.filter import SignalFilter

    try:
        # Level 0: Three-level dedup (before SignalFilter)
        from src.application.dedup import deduplicate_articles

        deduped = deduplicate_articles(pre_fetched_articles)

        # Layer 1: Signal Filter
        signal_filter = SignalFilter()
        filtered = signal_filter.filter(deduped)

        # --- Layer 2: Classify + Translate (LLM) ---
        # Candidate tags derived from template heading structure
        tag_list = "\n".join(heading_tree.titles)

        # Use BatchClassifyChain for batching + concurrency
        # Note: chain.ainvoke mutates filtered in-place, adding .tags and .translation
        from src.application.report.classify import BatchClassifyChain

        chain = BatchClassifyChain(
            tag_list=tag_list,
            target_lang=target_lang,
            batch_size=50,
            max_concurrency=5,
        )
        await chain.ainvoke(filtered)

        # Layer 3: Build clusters incrementally via add_articles
        report_data = ReportData(
            clusters={},
            date_range={"since": since, "until": until},
            target_lang=target_lang,
            heading_tree=heading_tree,
        )
        report_data.add_articles(filtered, lambda a: a.tags[0] if a.tags else "unknown")
        report_data.build(heading_tree)

        return report_data
    except Exception as e:
        logger.error(f"Entity clustering failed: {e}")
        raise


def cluster_articles_for_report(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
    heading_tree: HeadingNode | None = None,
) -> ReportData:
    """Fetch and cluster articles for an entity-based report.

    Returns:
        ReportData with clusters, date_range, target_lang, heading_tree.
    """
    articles = list_articles(
        limit=limit,
        since=since,
        until=until,
    )
    return asyncio.run(
        _entity_report_async(
            articles, since, until, auto_summarize, target_lang, heading_tree
        )
    )


__all__ = [
    "ReportArticle",
    "ReportCluster",
    "ReportData",
]
