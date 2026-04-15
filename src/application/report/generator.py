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
        # Level 0: Streaming dedup (before SignalFilter) - memory efficient
        from src.application.dedup import dedup_streaming

        deduped = dedup_streaming(pre_fetched_articles)

        # Layer 1: Signal Filter
        signal_filter = SignalFilter()
        filtered = signal_filter.filter(deduped)

        # --- Layer 2-4: LCEL chain composition ---
        from src.application.report.insight import InsightChain
        from src.application.report.models import BuildReportDataChain

        first_heading = (
            heading_tree.children[0].title
            if heading_tree and heading_tree.children
            else "其他"
        )
        # If first_heading is a Jinja2 placeholder (dynamic template), use "其他"
        if "{{" in first_heading or "{%" in first_heading:
            first_heading = "其他"
        chain = BuildReportDataChain(
            heading_tree=heading_tree,
            target_lang=target_lang,
            fallback_tag=first_heading,
        ) | InsightChain(top_n=100, target_lang=target_lang)

        report_data = await chain.ainvoke(filtered)
        report_data.date_range = {"since": since, "until": until}
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
