"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from src.application.report import (
    ArticleEnriched,
    EntityTag,
    EntityTopic,
    ReportData,
    SignalFilter,
)
from src.storage import list_articles

logger = logging.getLogger(__name__)

# Five-layer cake taxonomy (internal keys are always zh)
LAYER_KEYS = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"]

# Localized layer names
LAYER_NAMES = {
    "zh": ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"],
    "en": ["AI Application", "AI Model", "AI Infrastructure", "Chip", "Energy"],
}

LANG_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}


# ---------------------------------------------------------------------------
# v2 report helpers — topic clustering
# ---------------------------------------------------------------------------

# Keywords for Section B (signals) rule-based classification
_LEVERAGE_KEYWORDS = [
    "tool",
    "platform",
    "api",
    "framework",
    "open source",
    "library",
    "sdk",
    "model",
    "release",
    "launch",
    "github",
    "npm",
    "pypi",
    "runtime",
    "compiler",
    "assistant",
    "agent",
    "claude",
    "gpt",
    "gemini",
    "openai",
    "anthropic",
]
_BUSINESS_KEYWORDS = [
    "startup",
    "funding",
    "raise",
    "series",
    "ipo",
    "business model",
    "revenue",
    "unicorn",
    "vc",
    "venture",
    "investor",
    "seed round",
    " Series A",
    " Series B",
    "acqui-hire",
    "acquisition",
    "merger",
    "profit",
]

# Keywords for Section C (creation) rule-based classification
_CREATION_KEYWORDS = [
    "how to",
    "tutorial",
    "review",
    "top",
    "best",
    "vs",
    "comparison",
    "guide",
    "introduction",
    "beginner",
    "getting started",
    "101",
    "cheat sheet",
    "tips",
    "master",
    "learn",
    "course",
    "workshop",
]


def _classify_signal_leverage(article: dict) -> bool:
    """Rule-based check if article is about developer tools / AI platforms."""
    text = (
        article.get("title", "")
        + " "
        + article.get("summary", "")
        + " "
        + article.get("description", "")
    ).lower()
    return any(kw in text for kw in _LEVERAGE_KEYWORDS)


def _classify_signal_business(article: dict) -> bool:
    """Rule-based check if article is about startups / funding / business."""
    text = (
        article.get("title", "")
        + " "
        + article.get("summary", "")
        + " "
        + article.get("description", "")
    ).lower()
    return any(kw in text for kw in _BUSINESS_KEYWORDS)


def _classify_creation(article: dict) -> bool:
    """Rule-based check if article is a tutorial / how-to / review / best-of."""
    text = (
        article.get("title", "")
        + " "
        + article.get("summary", "")
        + " "
        + article.get("description", "")
    ).lower()
    return any(kw in text for kw in _CREATION_KEYWORDS)


# Template directory
DEFAULT_TEMPLATE_DIR = Path("~/.config/feedship/templates").expanduser()
DEFAULT_TEMPLATE_NAME = "default"


async def _entity_report_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
) -> dict[str, Any]:
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
        group_by_dimension,
        group_by_layer,
        render_entity_report,
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

        # Candidate tags for AI tech news classification
        tag_list = "\n".join(
            [
                "AI应用",
                "AI模型",
                "AI基础设施",
                "芯片",
                "能源",
                "LLM",
                "开源",
                "融资",
                "收购",
                "研究",
                "产品发布",
                "政策监管",
                "学术",
                "开发者工具",
                "创业公司",
            ]
        )

        async def process_batch(
            batch_articles: list[dict], batch_offset: int, semaphore: asyncio.Semaphore
        ) -> list[ClassifyTranslateItem]:
            """Process a single batch: build news_list and call LLM."""
            async with semaphore:
                news_list = "\n".join(
                    f"{i + 1}. {art.get('title', '')}"
                    for i, art in enumerate(batch_articles)
                )
                chain = get_classify_translate_chain(
                    tag_list=tag_list, news_list=news_list, target_lang=target_lang
                )
                result: ClassifyTranslateOutput = await chain.ainvoke({})
                # Adjust item IDs to account for batch offset
                for item in result.items:
                    item.id += batch_offset
                return result.items

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

        # Convert ClassifyTranslateOutput to EntityTopic[]
        # id is 1-indexed position in news_list, map back to original article
        # Group by primary tag (tags[0]) or feed_id if no tags
        _DIMENSION_KEYWORDS = {
            "release": [
                "release",
                "launch",
                "announce",
                "发布",
                "推出",
                "launches",
                "unveils",
            ],
            "funding": [
                "funding",
                "raise",
                "series",
                "vc",
                "invest",
                "融资",
                "投资",
                "raises",
            ],
            "research": [
                "research",
                "paper",
                "study",
                "benchmark",
                "研究",
                "论文",
                "arxiv",
            ],
            "ecosystem": [
                "open source",
                "github",
                "acquisition",
                "merger",
                "partnership",
                "生态",
                "开源",
                "收购",
            ],
            "policy": ["regulation", "policy", "government", "ban", "监管", "政策"],
        }

        def _classify_dim(article: dict) -> list[str]:
            text = (
                (article.get("title", "") or "")
                + " "
                + (article.get("summary", "") or "")
            ).lower()
            dims = []
            for dim, kws in _DIMENSION_KEYWORDS.items():
                if any(kw in text for kw in kws):
                    dims.append(dim)
            return dims if dims else ["ecosystem"]

        # Group by primary tag (or feed_id as fallback)
        from collections import defaultdict

        tag_groups: dict[str, list[tuple[int, dict]]] = defaultdict(
            list
        )  # tag -> [(item_id, article_dict)]
        for item in classify_output.items:
            if item.id <= len(filtered):
                art = filtered[item.id - 1]
                primary_tag = (
                    item.tags[0] if item.tags else art.get("feed_id", "unknown")
                )
                tag_groups[primary_tag].append((item.id, art))

        # Also store translated title per item_id
        trans_by_id = {item.id: item.translation for item in classify_output.items}

        # Build EntityTopic for each tag group
        entity_topics: list = []
        from src.application.report.models import (
            ArticleEnriched,
            EntityTopic,
        )

        for tag, items in tag_groups.items():
            arts = [item[1] for item in items]
            # Build ArticleEnriched for each article
            article_enriched_list = []
            for art in arts:
                ae = ArticleEnriched(
                    id=art.get("id", ""),
                    title=art.get("title", ""),
                    link=art.get("link", ""),
                    summary=art.get("summary", ""),
                    quality_score=art.get("quality_score", 0.0),
                    feed_weight=art.get("feed_weight", 0.0),
                    published_at=art.get("published_at", ""),
                    feed_id=art.get("feed_id", ""),
                    entities=[],  # No entities available from classify_translate
                    dimensions=_classify_dim(art),
                )
                article_enriched_list.append(ae)

            # Group by dimension
            by_dim: dict[str, list[ArticleEnriched]] = {}
            for ae in article_enriched_list:
                for dim in ae.dimensions:
                    by_dim.setdefault(dim, []).append(ae)

            # Find best article by quality for headline
            best_art = max(arts, key=lambda a: a.get("quality_score", 0.0))
            best_idx = next(
                i for i, a in enumerate(arts) if a.get("id") == best_art.get("id")
            )
            item_id = items[best_idx][0]
            headline = trans_by_id.get(item_id, tag)[:30]

            entity_topics.append(
                EntityTopic(
                    entity_id=tag,
                    entity_name=tag,
                    layer="AI应用",
                    headline=headline,
                    dimensions=by_dim,
                    articles_count=len(arts),
                    signals=[],
                    tldr="",
                    quality_weight=sum(a.get("quality_score", 0.0) for a in arts)
                    * len(arts),
                )
            )

        # Layer 3: TLDR Generation (top 10)
        tldr_gen = TLDRGenerator(top_n=10)
        tldr_top10 = await tldr_gen.generate_top10(entity_topics, target_lang)

        # Layer 4: Render
        rendered = await render_entity_report(
            tldr_top10, since, until, target_lang, template_name="entity"
        )

        # Build CLI-compatible layers structure from entity topics
        # Each EntityTopic -> topic dict with "sources" (flattened from dimensions)
        entity_topic_dicts: list[dict] = []
        for topic in entity_topics:
            # Flatten all articles from all dimensions into sources (as dicts)
            sources = []
            for dim_arts in topic.dimensions.values():
                for art in dim_arts:
                    sources.append(
                        {
                            "id": art.id,
                            "title": art.title,
                            "link": art.link,
                            "summary": art.summary,
                            "quality_score": art.quality_score,
                            "feed_weight": art.feed_weight,
                            "published_at": art.published_at,
                            "feed_id": art.feed_id,
                            "entities": [
                                {
                                    "name": e.name,
                                    "type": e.type,
                                    "normalized": e.normalized,
                                }
                                for e in art.entities
                            ],
                        }
                    )
            topic_dict = {
                "title": topic.entity_name,
                "headline": topic.headline,
                "layer": topic.layer,
                "signals": topic.signals,
                "sources": sources,
            }
            entity_topic_dicts.append(topic_dict)

        # Group entity topic dicts by layer (same structure as thematic pipeline)
        articles_by_layer: dict[str, list[dict]] = {cat: [] for cat in LAYER_KEYS}
        for topic_dict in entity_topic_dicts:
            layer = topic_dict.get("layer", "AI应用")
            if layer in articles_by_layer:
                articles_by_layer[layer].append(topic_dict)

        layers_data: list[dict] = []
        for layer_name in LAYER_KEYS:
            layers_data.append(
                {
                    "name": layer_name,
                    "topics": articles_by_layer.get(layer_name, []),
                }
            )

        # Rule-based signal classification on all entity sources
        all_sources = []
        for topic_dict in entity_topic_dicts:
            all_sources.extend(topic_dict.get("sources", []))

        leverage_articles = [a for a in all_sources if _classify_signal_leverage(a)]
        business_articles = [a for a in all_sources if _classify_signal_business(a)]
        creation_articles = [a for a in all_sources if _classify_creation(a)]

        signals_data = {"leverage": leverage_articles, "business": business_articles}
        creation_data = (
            [{"name": "创作选题", "topics": []}] if creation_articles else []
        )

        return {
            "rendered": rendered,
            "tldr_top10": tldr_top10,
            "layers": layers_data,
            "signals": signals_data,
            "creation": creation_data,
            "by_layer": group_by_layer(entity_topics),
            "by_dimension": group_by_dimension(entity_topics),
            "entity_topics": entity_topics,
            "date_range": {"since": since, "until": until},
        }
    except Exception as e:
        logger.error(f"Entity clustering failed: {e}")
        raise


def cluster_articles_for_report(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Fetch and cluster articles for an entity-based report.

    Returns:
        dict with keys: rendered (markdown str), tldr_top10, by_layer,
        by_dimension, entity_topics, date_range ({since, until}).
    """
    articles = list_articles(
        limit=limit,
        since=since,
        until=until,
    )
    # Convert ArticleListItem to dict for downstream pipeline
    article_dicts = [
        {
            "id": a.id,
            "feed_id": a.feed_id,
            "feed_name": a.feed_name,
            "feed_weight": a.feed_weight,
            "title": a.title,
            "link": a.link,
            "published_at": a.published_at,
            "description": a.description,
            "content": a.content,
            "summary": a.summary,
            "quality_score": a.quality_score,
            "feed_url": a.feed_url,
            "content_hash": a.content_hash,
            "minhash_signature": a.minhash_signature,
        }
        for a in articles
    ]
    return asyncio.run(
        _entity_report_async(article_dicts, since, until, auto_summarize, target_lang)
    )


async def render_report(
    data: dict[str, Any],
    template_name: str = "v2",
    target_lang: str = "zh",
) -> str:
    """Render a v2 report using Jinja2 template.

    Args:
        data: Report data from cluster_articles_for_report()
        template_name: Template name (without extension)
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        Rendered markdown string.
    """

    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        logger.error("Jinja2 not installed: pip install jinja2")
        raise

    template_path = DEFAULT_TEMPLATE_DIR / f"{template_name}.md"
    if template_path.exists():
        env = Environment(
            loader=FileSystemLoader(template_path.parent),
            autoescape=False,
        )
        template = env.get_template(template_path.name)
    else:
        logger.error("v2 template not found at %s", template_path)
        raise FileNotFoundError(
            f"Template '{template_name}' not found at {template_path}"
        )

    return template.render(
        layers=data.get("layers", []),
        signals=data.get("signals", {}),
        creation=data.get("creation", []),
        date_range=data.get("date_range", {}),
        target_lang=target_lang,
    )


__all__ = [
    "ArticleEnriched",
    "EntityTag",
    "EntityTopic",
    "ReportData",
    "SignalFilter",
]
