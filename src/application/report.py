"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from src.application.summarize import summarize_article_content
from src.llm.chains import (
    get_classify_chain,
    get_layer_summary_chain,
    get_topic_title_chain,
    get_translate_chain,
)
from src.storage import list_articles_for_llm, update_article_llm

logger = logging.getLogger(__name__)

# Five-layer cake taxonomy (internal keys are always zh)
LAYER_KEYS = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"]

# Localized layer names
LAYER_NAMES = {
    "zh": ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"],
    "en": ["AI Application", "AI Model", "AI Infrastructure", "Chip", "Energy"],
}

LANG_NAMES = {"zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean"}


def _lang_name(code: str) -> str:
    """Return human-readable language name for LLM prompts."""
    return LANG_NAMES.get(code, "Chinese")


def _layer_names(lang: str) -> list[str]:
    """Return layer category names in the specified language."""
    return LAYER_NAMES.get(lang, LAYER_NAMES["zh"])


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


def _keyword_overlap(title1: str, title2: str) -> float:
    """Compute simple keyword overlap between two titles (0.0–1.0)."""
    words1 = set(title1.lower().split())
    words2 = set(title2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


async def _cluster_articles_into_topics(
    articles: list[dict],
    target_lang: str,
) -> list[dict]:
    """Group articles into topics by theme within a layer.

    Clustering strategy:
      1. Group by feed_id (same source = same topic).
      2. Merge small clusters (<=2 articles) with nearest neighbour by
         title similarity (keyword overlap >= 0.2).
      3. Generate a short topic title via get_topic_title_chain.

    Each topic dict has keys: title, sources (list of article dicts),
    sources_count, insight (empty str, filled later by caller).
    """
    if not articles:
        return []

    # Step 1 — group by feed_id
    feed_groups: dict[str, list[dict]] = {}
    for a in articles:
        fid = a.get("feed_id") or a.get("feed_id") or "unknown"
        feed_groups.setdefault(fid, []).append(a)

    topics: list[dict] = []
    for _fid, arts in feed_groups.items():
        topics.append(
            {
                "title": "",  # filled below
                "sources": arts,
                "sources_count": len(arts),
                "insight": "",
            }
        )

    # Step 2 — merge small clusters with nearest neighbour
    merged = True
    while merged:
        merged = False
        new_topics: list[dict] = []
        skip = set()
        for i, t1 in enumerate(topics):
            if i in skip:
                continue
            if t1["sources_count"] <= 2:
                # find nearest neighbour
                best_score = 0.2  # minimum threshold
                best_j = -1
                for j, t2 in enumerate(topics):
                    if j == i or j in skip:
                        continue
                    titles_i = " ".join(a.get("title", "") for a in t1["sources"])
                    titles_j = " ".join(a.get("title", "") for a in t2["sources"])
                    score = _keyword_overlap(titles_i, titles_j)
                    if score > best_score:
                        best_score = score
                        best_j = j
                if best_j >= 0:
                    # merge t1 into t2
                    t2 = topics[best_j]
                    t2["sources"].extend(t1["sources"])
                    t2["sources_count"] = len(t2["sources"])
                    skip.add(i)
                    skip.add(best_j)
                    new_topics.append(t2)
                    merged = True
                else:
                    new_topics.append(t1)
            else:
                new_topics.append(t1)
        if merged:
            # remove duplicates that were merged multiple times
            seen = set()
            filtered = []
            for t in new_topics:
                key = id(t)
                if key not in seen:
                    seen.add(key)
                    filtered.append(t)
            topics = filtered
            merged = True  # loop again in case new small clusters formed

    # Deduplicate final list
    final: list[dict] = []
    seen_ids: set[int] = set()
    for t in topics:
        for a in t["sources"]:
            aid = id(a)
            if aid not in seen_ids:
                seen_ids.add(aid)
                final.append(t)
                break

    # Step 3 — generate topic titles via LLM
    semaphore = asyncio.Semaphore(5)

    async def title_for(topic: dict) -> dict:
        async with semaphore:
            article_list = "\n".join(
                f"- {a.get('title', 'Untitled')}" for a in topic["sources"][:8]
            )
            try:
                chain = get_topic_title_chain()
                title = await chain.ainvoke(
                    {
                        "article_list": article_list,
                        "target_lang": _lang_name(target_lang),
                    }
                )
                topic["title"] = title.strip()
            except Exception as e:
                logger.warning("Topic title generation failed: %s", e)
                # Fallback: use first article title
                topic["title"] = (
                    topic["sources"][0].get("title", "Misc")[:20]
                    if topic["sources"]
                    else "Misc"
                )
        return topic

    titled = await asyncio.gather(
        *[title_for(t) for t in final], return_exceptions=True
    )
    result: list[dict] = []
    for t in titled:
        if isinstance(t, Exception):
            logger.warning("Topic title task failed: %s", t)
            continue
        result.append(t)

    return result


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


def _is_chinese(text: str) -> bool:
    """Detect if text contains Chinese characters."""
    return bool(re.search(r"[\u4e00-\u9fff]", text))


# In-memory cache for title translations to avoid repeated LLM calls
_title_translate_cache: dict[tuple[str, str], str] = {}


def _translate_title_sync(title: str, target_lang: str) -> str:
    """Translate article title to target language (sync, for template use)."""
    if target_lang == "zh":
        return title
    cache_key = (title, target_lang)
    if cache_key in _title_translate_cache:
        return _title_translate_cache[cache_key]

    import asyncio
    import concurrent.futures

    async def _translate():
        chain = get_translate_chain()
        return await chain.ainvoke({"text": title, "target_lang": target_lang})

    def _run():
        loop = asyncio.new_event_loop()
        try:
            return asyncio.run(_translate())
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(_run)
        translated = future.result()

    _title_translate_cache[cache_key] = translated
    return translated


def _format_article_title(title: str, target_lang: str) -> str:
    """Format article title with translation if needed.

    Returns:
        - title (if target_lang == zh or title is not Chinese)
        - title（translated）if title is Chinese and target_lang != zh
    """
    if target_lang == "zh" or not _is_chinese(title):
        return title
    translated = _translate_title_sync(title, target_lang)
    return f"{title}（{translated}）"


# Template directory
DEFAULT_TEMPLATE_DIR = Path("~/.config/feedship/templates").expanduser()
DEFAULT_TEMPLATE_NAME = "default"


async def classify_article_layer(text: str, title: str = "") -> str:
    """Classify an article into one of the AI five-layer cake categories.

    Returns one of: AI应用, AI模型, AI基础设施, 芯片, 能源
    """
    sample = " ".join(text.split()[:300])
    try:
        chain = get_classify_chain()
        result = await chain.ainvoke({"title": title, "content": sample})
        # Match against known categories
        for cat in LAYER_KEYS:
            if cat in result:
                return cat
        # Fallback: return first match or default
        for cat in LAYER_KEYS:
            if cat.split("(")[0].strip() in result:
                return cat
        logger.warning("Could not classify article layer from: %s", result.strip())
        return "AI应用"  # Default fallback
    except Exception as e:
        logger.warning("Failed to classify article layer: %s", e)
        return "AI应用"


async def generate_cluster_summary(
    articles: list[dict], layer: str, target_lang: str = "zh"
) -> str:
    """Generate a 2-3 paragraph summary for a cluster of articles.

    Args:
        articles: List of article dicts with title, summary, link, quality_score.
        layer: The layer category name.
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        A paragraph summarizing the articles in this cluster.
    """
    if not articles:
        return ""

    # Build article list for prompt
    article_list = "\n".join(
        f"- {a.get('title', 'Untitled')} (q={a.get('quality_score') or 0:.2f})"
        for a in articles[:10]  # Max 10 articles in prompt
    )

    # Retry with exponential backoff: 2s, 4s, 8s
    delays = [2, 4, 8]
    for attempt, delay in enumerate(delays):
        try:
            chain = get_layer_summary_chain()
            return await chain.ainvoke(
                {
                    "layer": layer,
                    "article_list": article_list,
                    "target_lang": _lang_name(target_lang),
                }
            )
        except Exception as e:
            if attempt < len(delays) - 1:
                logger.warning(
                    "Cluster summary attempt %d failed: %s. Retrying in %ds...",
                    attempt + 1,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    "Cluster summary all %d attempts failed: %s. Returning fallback.",
                    len(delays),
                    e,
                )

    # After 3 failures, return language-aware fallback
    fallbacks = {
        "zh": "（本周暂无重大进展）",
        "en": "(No significant developments this week)",
        "ja": "（今週の重大な展開なし）",
        "ko": "（이번 주 중요한 발전 없음）",
    }
    return fallbacks.get(target_lang, fallbacks["zh"])


def cluster_articles_for_report(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Fetch and cluster articles for a report date range.

    Args:
        since: Start date YYYY-MM-DD
        until: End date YYYY-MM-DD
        limit: Max articles to process
        auto_summarize: If True, summarize unsummarized articles on-demand
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        dict with keys: articles_by_layer (dict of layer -> list),
        layer_summaries (dict of layer -> summary text), date_range,
        summarized_on_demand (count of articles summarized during generation)
    """
    # Fetch ALL articles in date range (unsummarized_only=False)
    # On-demand summarize handles weight-based gating inside _cluster_articles_async
    articles = list_articles_for_llm(
        limit=limit,
        since=since,
        until=until,
        unsummarized_only=False,
    )

    return asyncio.run(
        _cluster_articles_async(articles, since, until, auto_summarize, target_lang)
    )


async def _cluster_articles_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Async helper to cluster articles by layer."""
    # Use pre-fetched articles directly (from cluster_articles_for_report)
    articles = pre_fetched_articles

    # Classify each article into a layer
    results: dict[str, list] = {cat: [] for cat in LAYER_KEYS}
    summarized_on_demand: int = 0

    async def process_one(article: dict) -> tuple[str, dict]:
        # Use article fields directly from pre-fetched list (no redundant DB query)
        full = article
        summary = full.get("summary") or ""
        title = full.get("title", "")
        feed_weight = full.get("feed_weight", 0)

        # On-demand summarize if missing AND feed weight >= 0.7
        nonlocal summarized_on_demand
        if not summary and auto_summarize and feed_weight >= 0.7:
            content = full.get("content") or full.get("description") or ""
            if content:
                try:
                    summary, _, quality, _ = await summarize_article_content(
                        content, title
                    )
                    full["summary"] = summary
                    full["quality_score"] = quality
                    summarized_on_demand += 1
                    # Persist to database
                    update_article_llm(
                        article["id"],
                        summary=summary,
                        quality_score=quality,
                        keywords=[],
                        tags=[],
                    )
                except Exception as e:
                    logger.warning(
                        "On-demand summarize failed for %s: %s", article["id"], e
                    )

        text = summary or full.get("content") or full.get("description") or ""
        layer = await classify_article_layer(text, title)
        return layer, {
            "id": article["id"],
            "title": title,
            "link": full.get("link", ""),
            "summary": full.get("summary", ""),
            "quality_score": full.get("quality_score"),
            "published_at": full.get("published_at"),
        }

    semaphore = asyncio.Semaphore(10)

    async def bounded_process(a: dict) -> tuple[str, dict]:
        async with semaphore:
            return await process_one(a)

    if articles:
        classified = await asyncio.gather(
            *[bounded_process(a) for a in articles],
            return_exceptions=True,
        )
        for item in classified:
            if isinstance(item, Exception):
                continue
            layer, article_dict = item
            if layer in results:
                results[layer].append(article_dict)

    # Generate summaries for each layer
    layer_summaries: dict[str, str] = {}
    for layer, arts in results.items():
        if arts:
            layer_summaries[layer] = await generate_cluster_summary(
                arts, layer, target_lang
            )

    return {
        "articles_by_layer": results,
        "layer_summaries": layer_summaries,
        "date_range": {"since": since, "until": until},
        "summarized_on_demand": summarized_on_demand,
    }


# ---------------------------------------------------------------------------
# v2 report — topic clustering + signals + creation
# ---------------------------------------------------------------------------


async def _cluster_articles_v2_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
) -> dict[str, Any]:
    """Async implementation of v2 clustering with topic grouping."""
    articles = pre_fetched_articles
    articles_by_layer: dict[str, list[dict]] = {cat: [] for cat in LAYER_KEYS}

    # Also collect all articles flat (for signals / creation classification)
    all_processed: list[dict] = []

    async def process_one(article: dict) -> tuple[str, dict, dict]:
        # Use article fields directly from pre-fetched list (no redundant DB query)
        full = article
        summary = full.get("summary") or ""
        title = full.get("title", "")
        feed_weight = full.get("feed_weight", 0)
        feed_id = full.get("feed_id", "unknown")

        if not summary and auto_summarize and feed_weight >= 0.7:
            content = full.get("content") or full.get("description") or ""
            if content:
                try:
                    summary, _, quality, _ = await summarize_article_content(
                        content, title
                    )
                    full["summary"] = summary
                    full["quality_score"] = quality
                    update_article_llm(
                        article["id"],
                        summary=summary,
                        quality_score=quality,
                        keywords=[],
                        tags=[],
                    )
                except Exception as e:
                    logger.warning(
                        "On-demand summarize failed for %s: %s", article["id"], e
                    )

        text = summary or full.get("content") or full.get("description") or ""
        layer = await classify_article_layer(text, title)

        processed = {
            "id": article["id"],
            "title": title,
            "link": full.get("link", ""),
            "summary": full.get("summary", ""),
            "quality_score": full.get("quality_score"),
            "published_at": full.get("published_at"),
            "feed_id": feed_id,
            "layer": layer,
        }
        return layer, processed, processed

    semaphore = asyncio.Semaphore(10)

    async def bounded_process(a: dict) -> tuple[str, dict, dict]:
        async with semaphore:
            return await process_one(a)

    if articles:
        classified = await asyncio.gather(
            *[bounded_process(a) for a in articles],
            return_exceptions=True,
        )
        for item in classified:
            if isinstance(item, Exception):
                continue
            layer, processed, _ = item
            if layer in articles_by_layer:
                articles_by_layer[layer].append(processed)
            all_processed.append(processed)

    # Cluster articles into topics within each layer
    layers_data: list[dict] = []
    for layer_name in LAYER_KEYS:
        arts = articles_by_layer.get(layer_name, [])
        topics = await _cluster_articles_into_topics(arts, target_lang)
        layers_data.append(
            {
                "name": layer_name,
                "topics": topics,
            }
        )

    # Section B — signals
    leverage_topics: list[dict] = []
    business_topics: list[dict] = []
    for article in all_processed:
        if _classify_signal_leverage(article):
            leverage_topics.append(article)
        elif _classify_signal_business(article):
            business_topics.append(article)

    # Section C — creation
    creation_sections: list[dict] = []
    creation_arts = [a for a in all_processed if _classify_creation(a)]
    if creation_arts:
        # Cluster creation articles into a single "创作选题" section
        creation_topics = await _cluster_articles_into_topics(
            creation_arts, target_lang
        )
        creation_sections.append(
            {
                "name": "创作选题",
                "topics": creation_topics,
            }
        )

    return {
        "layers": layers_data,
        "signals": {
            "leverage": leverage_topics,
            "business": business_topics,
        },
        "creation": creation_sections,
        "date_range": {"since": since, "until": until},
    }


def cluster_articles_for_report_v2(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Fetch and cluster articles for a v2 report with topic clustering.

    Returns:
        dict with keys: layers (list of {name, topics}), signals
        ({leverage, business}), creation (list of {name, topics}),
        date_range ({since, until}).
    """
    articles = list_articles_for_llm(
        limit=limit,
        since=since,
        until=until,
        unsummarized_only=False,
    )
    return asyncio.run(
        _cluster_articles_v2_async(articles, since, until, auto_summarize, target_lang)
    )


def render_report_v2(
    data: dict[str, Any],
    template_name: str = "v2",
    target_lang: str = "zh",
) -> str:
    """Render a v2 report using Jinja2 template.

    Args:
        data: Report data from cluster_articles_for_report_v2()
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


def render_report(
    data: dict[str, Any],
    template_name: str = DEFAULT_TEMPLATE_NAME,
    target_lang: str = "zh",
) -> str:
    """Render a report using Jinja2 template.

    Args:
        data: Report data from cluster_articles_for_report()
        template_name: Template name (without extension)
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        Rendered markdown string.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, Template
    except ImportError:
        logger.error("Jinja2 not installed: pip install jinja2")
        raise

    # Find template
    template_path = DEFAULT_TEMPLATE_DIR / f"{template_name}.md"
    if not template_path.exists():
        # Create default template
        _create_default_template()
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
        # Fallback to built-in template
        template = Template(_DEFAULT_TEMPLATE_MARKDOWN)

    return template.render(
        articles_by_layer=data["articles_by_layer"],
        layer_summaries=data["layer_summaries"],
        date_range=data["date_range"],
        categories=_layer_names(target_lang),
        target_lang=target_lang,
    )


def _create_default_template() -> None:
    """Create the default template if it doesn't exist."""
    DEFAULT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    template_path = DEFAULT_TEMPLATE_DIR / f"{DEFAULT_TEMPLATE_NAME}.md"
    if not template_path.exists():
        template_path.write_text(_DEFAULT_TEMPLATE_MARKDOWN)
        logger.info("Created default template at %s", template_path)


async def _translate_report_async(report_text: str, target_lang: str) -> str:
    """Internal async translation implementation."""
    if target_lang == "zh":
        return report_text

    chain = get_translate_chain()
    lines = report_text.splitlines()
    translated_lines = []

    for line in lines:
        # Preserve article bullet points (lines containing link pattern)
        if "]((" in line or "](http" in line or "](https" in line:
            translated_lines.append(line)
        else:
            result = await chain.ainvoke({"text": line, "target_lang": target_lang})
            translated_lines.append(result)

    return "\n".join(translated_lines)


def translate_report(report_text: str, target_lang: str) -> str:
    """Translate report text to target language.

    Args:
        report_text: The rendered report text.
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        Translated report text, or original if target_lang is "zh".
    """
    if target_lang == "zh":
        return report_text

    import asyncio
    import concurrent.futures

    def _run():
        loop = asyncio.new_event_loop()
        try:
            return asyncio.run(_translate_report_async(report_text, target_lang))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(_run)
        return future.result()


# Built-in default template (used when file not found)
_DEFAULT_TEMPLATE_MARKDOWN = """\
# AI 日报 — {{ date_range.since }} ~ {{ date_range.until }}

{% set layer_keys = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"] %}
{% for layer_name in categories %}
{% set layer = layer_keys[loop.index0] %}
{% set articles = articles_by_layer.get(layer, []) %}
{% set summary = layer_summaries.get(layer, "") %}
{% if articles and summary and summary|trim %}
### {{ loop.index }}. {{ layer_name }}

{{ summary }}

{% for article in articles[:10] %}
- [{{ article.title | format_title }}]({{ article.link }}) (q={{ "%.2f"|format(article.quality_score or 0) }})
{% endfor %}

{% endif %}
{% endfor %}
"""
