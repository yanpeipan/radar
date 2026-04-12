"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

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
from src.llm.output_models import ClassifyTranslateItem
from src.storage import list_articles

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# v2 report helpers — topic clustering
# ---------------------------------------------------------------------------

# Template directory
DEFAULT_TEMPLATE_DIR = Path("~/.config/feedship/templates").expanduser()
DEFAULT_TEMPLATE_NAME = "default"


def _build_news_list(batch_articles: list[ArticleListItem]) -> str:
    """Build news_list string from a batch of articles (1-indexed)."""
    return "\n".join(
        f"{i + 1}. {art.title or ''}" for i, art in enumerate(batch_articles)
    )


async def _run_classify_batch(
    batch: dict,
    tag_list: str,
    target_lang: str,
) -> list[ClassifyTranslateItem]:
    """Run a single batch through the classify+translate chain."""
    from src.llm.chains import get_classify_translate_chain

    batch_articles: list[ArticleListItem] = batch["batch_articles"]
    batch_offset: int = batch["batch_offset"]
    news_list = _build_news_list(batch_articles)
    chain = get_classify_translate_chain(
        tag_list=tag_list,
        news_list=news_list,
        target_lang=target_lang,
    )
    output = await chain.ainvoke(
        {
            "tag_list": tag_list,
            "news_list": news_list,
            "target_lang": target_lang,
        }
    )
    for item in output.items:
        item.id += batch_offset
    return output.items


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
    from src.llm.output_models import ClassifyTranslateOutput

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

        # Create all batches with their offset values
        batches = []
        for i in range(0, len(filtered), BATCH_SIZE):
            batch_articles = filtered[i : i + BATCH_SIZE]
            batches.append({"batch_articles": batch_articles, "batch_offset": i})

        # Process batches concurrently with semaphore limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def run_with_semaphore(batch: dict) -> list[ClassifyTranslateItem]:
            async with semaphore:
                try:
                    return await _run_classify_batch(batch, tag_list, target_lang)
                except Exception as e:
                    logger.warning(
                        "Batch %d failed: %s — returning empty list",
                        batch["batch_offset"],
                        e,
                    )
                    return []

        batch_results = await asyncio.gather(*[run_with_semaphore(b) for b in batches])

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
                    dimensions=[tag],
                    translation=trans_by_id.get(item_id, ""),
                )
                for item_id, art in items
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

        # Layer 4: Build clusters dict by traversing heading tree structure
        # heading_tree.children are the top-level sections (H2 headings)
        # Each heading's title maps to the matching ReportCluster from entity_topics
        # If no match, create an empty ReportCluster to preserve template structure

        def _tag_of(cluster: ReportCluster) -> str:
            return cluster.children[0].dimensions[0] if cluster.children else ""

        clusters: dict[str, list[ReportCluster]] = {}
        for node in heading_tree.children if heading_tree else []:
            matched = next(
                (c for c in entity_topics if _tag_of(c) == node.title),
                ReportCluster(name=node.title, children=[], articles=[]),
            )
            clusters.setdefault(node.title, []).append(matched)

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
    "EntityTag",
    "ReportCluster",
    "ReportData",
    "SignalFilter",
]
