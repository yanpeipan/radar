"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .template import HeadingNode

from src.application.articles import ArticleListItem
from src.application.report import (
    EntityTag,
    ReportArticle,
    ReportCluster,
    ReportData,
    SignalFilter,
)
from src.storage import list_articles

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v2 report helpers — topic clustering
# ---------------------------------------------------------------------------

# Template directory
DEFAULT_TEMPLATE_DIR = Path("~/.config/feedship/templates").expanduser()
DEFAULT_TEMPLATE_NAME = "default"


async def _entity_report_async(
    pre_fetched_articles: list[ArticleListItem],
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
    heading_tree: "HeadingNode | None" = None,
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
    from src.application.report.render import (
        group_clusters,
    )
    from src.application.report.tldr import TLDRGenerator
    from src.llm.chains import get_classify_translate_chain
    from src.llm.output_models import ClassifyTranslateItem, ClassifyTranslateOutput

    try:
        # Level 0: Three-level dedup (before SignalFilter)
        from src.application.dedup import deduplicate_articles

        deduped = deduplicate_articles(pre_fetched_articles)

        # Layer 1: Signal Filter
        signal_filter = SignalFilter()
        filtered = signal_filter.filter(deduped)

        # --- Layer 2: Classify + Translate (LLM) ---
        # Split filtered into batches of 50, process up to 5 concurrently
        BATCH_SIZE = 50
        MAX_CONCURRENT = 5

        # Candidate tags derived from template heading structure
        tag_list = "\n".join(heading_tree.titles)

        async def process_batch(
            batch_articles: list[ArticleListItem],
            batch_offset: int,
            semaphore: asyncio.Semaphore,
        ) -> list[ClassifyTranslateItem]:
            """Process a single batch: build news_list and call LLM."""
            import json
            import re

            async with semaphore:
                try:
                    news_list = "\n".join(
                        f"{i + 1}. {art.title or ''}"
                        for i, art in enumerate(batch_articles)
                    )
                    chain = get_classify_translate_chain(
                        tag_list=tag_list, news_list=news_list, target_lang=target_lang
                    )
                    # Chain returns a string (StrOutputParser). Extract JSON array from
                    # potentially mixed output (the LLM sometimes outputs text before/after JSON).
                    raw_output = await chain.ainvoke(
                        {
                            "news_list": news_list,
                            "tag_list": tag_list,
                            "target_lang": target_lang,
                        }
                    )
                    # Try to find JSON array in the output
                    json_match = re.search(r"\[.*\]", raw_output, re.DOTALL)
                    if json_match:
                        parsed_dict = {"items": json.loads(json_match.group())}
                    else:
                        parsed_dict = {"items": []}
                    output = ClassifyTranslateOutput(**parsed_dict)
                    # Adjust item IDs to account for batch offset
                    for item in output.items:
                        item.id += batch_offset
                    return output.items
                except Exception as e:
                    logger.warning(
                        "Batch %d failed: %s — returning empty list", batch_offset, e
                    )
                    return []

        # Create all batches with their offset values
        batches = []
        for i in range(0, len(filtered), BATCH_SIZE):
            batch = filtered[i : i + BATCH_SIZE]
            batches.append((batch, i))  # (batch_articles, offset)

        # Process batches concurrently with semaphore limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        tasks = [process_batch(batch, offset, semaphore) for batch, offset in batches]
        batch_results = await asyncio.gather(*tasks)

        # Flatten all items into single list, preserving global ID order
        all_items: list[ClassifyTranslateItem] = []
        for batch_items in batch_results:
            all_items.extend(batch_items)

        # Convert to ClassifyTranslateOutput for downstream compatibility
        classify_output = ClassifyTranslateOutput(items=all_items)

        # Convert ClassifyTranslateOutput to ReportCluster[]
        # id is 1-indexed position in news_list, map back to original article
        # Group by primary tag (tags[0]) or feed_id if no tags
        # Group by primary tag (or feed_id as fallback)
        from collections import defaultdict

        tag_groups: dict[str, list[tuple[int, ArticleListItem]]] = defaultdict(
            list
        )  # tag -> [(item_id, ArticleListItem)]
        for item in classify_output.items:
            if item.id <= len(filtered):
                art = filtered[item.id - 1]
                primary_tag = item.tags[0] if item.tags else art.feed_id or "unknown"
                tag_groups[primary_tag].append((item.id, art))

        # Also store translated title per item_id
        trans_by_id = {item.id: item.translation for item in classify_output.items}

        # Build ReportCluster for each tag group
        entity_topics: list = []
        from src.application.report.models import (
            ReportArticle,
            ReportCluster,
        )

        for tag, items in tag_groups.items():
            arts = [item[1] for item in items]
            # Build ReportArticle for each article
            article_enriched_list = [
                ReportArticle(
                    id=art.id or "",
                    feed_id=art.feed_id or "",
                    feed_name=getattr(art, "feed_name", "") or "",
                    title=art.title or "",
                    link=art.link or "",
                    guid=getattr(art, "guid", "") or "",
                    published_at=art.published_at or "",
                    description=art.description or "",
                    tags=[],
                    dimensions=[tag],  # primary tag is the dimension
                )
                for art in arts
            ]

            # Find best article by quality for headline
            best_art = max(arts, key=lambda a: a.quality_score or 0.0)
            best_idx = next(i for i, a in enumerate(arts) if a.id == best_art.id)
            item_id = items[best_idx][0]
            headline = trans_by_id.get(item_id, tag)[:30]

            entity_topics.append(
                ReportCluster(
                    name=headline,
                    summary="",
                    tags=[],
                    children=article_enriched_list,
                    articles=article_enriched_list,
                )
            )

        # Layer 4: Render
        clusters = group_clusters(entity_topics)
        report_data = ReportData(
            clusters=clusters,
            date_range={"since": since, "until": until},
            target_lang=target_lang,
            heading_tree=heading_tree,
        )

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
    heading_tree: "HeadingNode | None" = None,
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
    "EntityTag",
    "ReportCluster",
    "ReportData",
    "SignalFilter",
]
