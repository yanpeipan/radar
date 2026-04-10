"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from src.application.entity_report import (
    ArticleEnriched,
    EntityClusterer,
    EntityTag,
    EntityTopic,
    NERExtractor,
    ReportData,
    SignalFilter,
    TLDRGenerator,
)
from src.llm.core import get_llm_client
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


def _clean_translation(text: str) -> str:
    """Strip thinking/analysis prefix from LLM translation response.

    MiniMax returns thinking blocks that pollute the clean translation.
    Extract the actual Chinese translation from the answer portion.
    """
    import re

    text = text.strip()

    # MiniMax thinking block embeds the user's prompt AND the answer.
    # The answer is typically in quotes like "Chinese translation".
    # Find all double-quoted strings containing Chinese, skip the prompt
    # (which has mixed Chinese+English with : between), return the pure Chinese one.
    quoted = re.findall(r'"([^"]*)"', text)
    for q in quoted:
        if re.search(r"[\u4e00-\u9fff]", q):
            # Skip if contains English letters (it's the prompt, not translation)
            if re.search(r"[a-zA-Z]", q):
                continue
            # Skip if too short (likely the prompt "直接翻译成中文，不要解释")
            if len(q.strip()) <= 10:
                continue
            q = re.sub(r"[.。]+$", "", q)
            if q.strip():
                return q.strip()

    # Fallback: find first Chinese character sequence after answer/答案 marker
    answer_match = re.search(
        r'(?:final answer|最后答案|answer|答案)[:：]\s*["\']?(.+?)(?:\n|$)',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if answer_match:
        result = answer_match.group(1).strip().strip('"').strip("'")
        result = re.sub(r"[.。]+$", "", result)
        if result and re.search(r"[\u4e00-\u9fff]", result):
            return result

    # Fallback: find first Chinese character and extract from there
    chinese_start = re.search(r"[\u4e00-\u9fff]", text)
    if chinese_start:
        result = text[chinese_start.start() :].strip()
        result = re.sub(r'["\']+$', "", result)
        result = re.sub(r"[.。]+$", "", result)
        if result:
            return result

    return text.strip().strip('"').strip("'")

    return text.strip().strip('"').strip("'")


def _is_chinese(text: str) -> bool:
    """Detect if text contains Chinese characters."""
    return bool(re.search(r"[\u4e00-\u9fff]", text))


# In-memory cache for title translations to avoid repeated LLM calls
_title_translate_cache: dict[tuple[str, str], str] = {}


def _translate_title_sync(title: str, target_lang: str) -> str:
    """Translate article title to target language (sync, for template use).

    Titles should be pre-translated by render_report
    before template rendering. This function only performs cache lookup
    to avoid asyncio.run_until_complete() misuse in async context.
    """
    cache_key = (title, target_lang)
    if cache_key in _title_translate_cache:
        return _title_translate_cache[cache_key]

    # Cache miss — pre-translation should have populated the cache.
    # Return original title as fallback; do NOT call async LLM from sync Jinja2 context.
    logger.warning(
        "Title translation cache miss for '%s' -> %s. "
        "Pre-translation may not have run correctly.",
        title[:50],
        target_lang,
    )
    return title


async def _translate_titles_batch_async(
    titles: list[str], target_lang: str
) -> dict[str, str]:
    """Pre-translate all titles in batch to avoid per-title event loop creation (Fix #5).

    Returns a dict mapping original title -> translated title.
    """
    if not titles:
        return {}
    client = get_llm_client()
    semaphore = asyncio.Semaphore(1)

    async def translate_one(title: str) -> tuple[str, str]:
        async with semaphore:
            prompt = f"直接翻译成中文，不要解释：{title}"
            result = await client.complete(prompt, max_tokens=300)
            cleaned = _clean_translation(result.strip())
            return (title, cleaned)

    results = await asyncio.gather(
        *[translate_one(t) for t in titles], return_exceptions=True
    )
    return {item[0]: item[1] for item in results if not isinstance(item, Exception)}


def _format_article_title(title: str, target_lang: str) -> str:
    """Format article title with translation if needed.

    Returns:
        - translated title (if title is not Chinese and target_lang != en)
        - title（translated）if title is Chinese and target_lang == en
        - title otherwise
    """
    if target_lang == "en" and _is_chinese(title):
        # Show English title when target is English, with Chinese original
        translated = _translate_title_sync(title, target_lang)
        return f"{title}（{translated}）"
    if target_lang != "en" and not _is_chinese(title):
        # Translate non-Chinese titles (e.g. English -> Chinese)
        return _translate_title_sync(title, target_lang)
    return title


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
    Layer 1: NER + Entity Resolution (LLM batch)
    Layer 2: Entity Clustering (LLM)
    Layer 3: TLDR Generation (1 LLM call)
    Layer 4: Render (Jinja2)
    """
    import logging

    logger = logging.getLogger(__name__)

    from src.application.report.entity_cluster import EntityClusterer
    from src.application.report.filter import SignalFilter
    from src.application.report.ner import NERExtractor
    from src.application.report.render import (
        group_by_dimension,
        group_by_layer,
        render_entity_report,
    )
    from src.application.report.tldr import TLDRGenerator

    try:
        # Layer 0: Signal Filter
        signal_filter = SignalFilter()
        filtered = signal_filter.filter(pre_fetched_articles)

        # Layer 1: NER + Enrich
        ner = NERExtractor(batch_size=20)
        enriched = await ner.extract_batch(filtered)

        # Layer 2: Entity Clustering
        clusterer = EntityClusterer()
        entity_topics = await clusterer.cluster(enriched, target_lang)

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
        env.filters["format_title"] = lambda title: _format_article_title(
            title, target_lang
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
    "NERExtractor",
    "EntityClusterer",
    "TLDRGenerator",
]
