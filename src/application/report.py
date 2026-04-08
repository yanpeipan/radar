"""Report generation — clustering articles and rendering Jinja2 templates."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from src.application.summarize import summarize_article_content
from src.llm.core import llm_complete
from src.storage import get_article_with_llm, list_articles_for_llm, update_article_llm

logger = logging.getLogger(__name__)

# Five-layer cake taxonomy
FIVE_LAYER_CATEGORIES = [
    "AI应用",  # Application
    "AI模型",  # Model
    "AI基础设施",  # Infrastructure
    "芯片",  # Chip
    "能源",  # Energy
]

# Template directory
DEFAULT_TEMPLATE_DIR = Path("~/.config/feedship/templates").expanduser()
DEFAULT_TEMPLATE_NAME = "default"


async def classify_article_layer(text: str, title: str = "") -> str:
    """Classify an article into one of the AI five-layer cake categories.

    Returns one of: AI应用, AI模型, AI基础设施, 芯片, 能源
    """
    prompt = f"""Classify this article into ONE of the following categories:

- AI应用 (Application): AI products, tools, and services used by end users
- AI模型 (Model): AI model releases, benchmarks, research papers, training methods
- AI基础设施 (Infrastructure): Cloud platforms, MLOps tools, deployment, APIs
- 芯片 (Chip): AI hardware, GPUs, custom silicon, semiconductor news
- 能源 (Energy): AI energy consumption, data center power, carbon, renewable energy

Article Title: {title}
Article Content (first 300 words):
{{content}}

Return ONLY the category name, nothing else. Choose the SINGLE most appropriate category."""

    sample = " ".join(text.split()[:300])
    try:
        result = await llm_complete(
            prompt.format(content=sample),
            max_tokens=15,
            temperature=0.1,
        )
        # Match against known categories
        for cat in FIVE_LAYER_CATEGORIES:
            if cat in result:
                return cat
        # Fallback: return first match or default
        for cat in FIVE_LAYER_CATEGORIES:
            if cat.split("(")[0].strip() in result:
                return cat
        logger.warning("Could not classify article layer from: %s", result.strip())
        return "AI应用"  # Default fallback
    except Exception as e:
        logger.warning("Failed to classify article layer: %s", e)
        return "AI应用"


async def generate_cluster_summary(articles: list[dict], layer: str) -> str:
    """Generate a 2-3 paragraph summary for a cluster of articles.

    Args:
        articles: List of article dicts with title, summary, link, quality_score.
        layer: The layer category name.

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

    prompt = f"""You are writing a concise summary for a news report section.

The following articles are about: {layer}

Articles:
{article_list}

Write 2-3 paragraphs summarizing the key trends and insights from these articles.
Focus on the most important developments. Use professional Chinese.

Summary:"""

    try:
        return await llm_complete(prompt, max_tokens=300, temperature=0.3)
    except Exception as e:
        logger.warning("Failed to generate cluster summary: %s", e)
        return "（暂无总结）"


def cluster_articles_for_report(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
) -> dict[str, Any]:
    """Fetch and cluster articles for a report date range.

    Args:
        since: Start date YYYY-MM-DD
        until: End date YYYY-MM-DD
        limit: Max articles to process
        auto_summarize: If True, summarize unsummarized articles on-demand

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

    return asyncio.run(_cluster_articles_async(articles, since, until, auto_summarize))


async def _cluster_articles_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool = True,
) -> dict[str, Any]:
    """Async helper to cluster articles by layer."""
    # Use pre-fetched articles directly (from cluster_articles_for_report)
    articles = pre_fetched_articles

    # Classify each article into a layer
    results: dict[str, list] = {cat: [] for cat in FIVE_LAYER_CATEGORIES}
    summarized_on_demand: int = 0

    async def process_one(article: dict) -> tuple[str, dict]:
        aid = article["id"]
        try:
            full = get_article_with_llm(aid)
        except Exception:
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
                    # Update local summary for text classification below
                    full["summary"] = summary
                    # Persist to database
                    update_article_llm(
                        aid,
                        summary=summary,
                        quality_score=quality,
                        keywords=[],
                        tags=[],
                    )
                except Exception as e:
                    logger.warning("On-demand summarize failed for %s: %s", aid, e)

        text = summary or full.get("content") or full.get("description") or ""
        layer = await classify_article_layer(text, title)
        return layer, {
            "id": aid,
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
            layer_summaries[layer] = await generate_cluster_summary(arts, layer)

    return {
        "articles_by_layer": results,
        "layer_summaries": layer_summaries,
        "date_range": {"since": since, "until": until},
        "summarized_on_demand": summarized_on_demand,
    }


def render_report(
    data: dict[str, Any],
    template_name: str = DEFAULT_TEMPLATE_NAME,
) -> str:
    """Render a report using Jinja2 template.

    Args:
        data: Report data from cluster_articles_for_report()
        template_name: Template name (without extension)

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
        template = env.get_template(template_path.name)
    else:
        # Fallback to built-in template
        template = Template(_DEFAULT_TEMPLATE_MARKDOWN)

    return template.render(
        articles_by_layer=data["articles_by_layer"],
        layer_summaries=data["layer_summaries"],
        date_range=data["date_range"],
        categories=FIVE_LAYER_CATEGORIES,
    )


def _create_default_template() -> None:
    """Create the default template if it doesn't exist."""
    DEFAULT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    template_path = DEFAULT_TEMPLATE_DIR / f"{DEFAULT_TEMPLATE_NAME}.md"
    if not template_path.exists():
        template_path.write_text(_DEFAULT_TEMPLATE_MARKDOWN)
        logger.info("Created default template at %s", template_path)


# Built-in default template (used when file not found)
_DEFAULT_TEMPLATE_MARKDOWN = """\
# AI 日报 — {{ date_range.since }} ~ {{ date_range.until }}

## A. AI五层蛋糕

{% for layer in ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"] %}
{% set articles = articles_by_layer.get(layer, []) %}
{% set summary = layer_summaries.get(layer, "") %}
{% if articles %}
### {{ loop.index }}. {{ layer }}

{{ summary }}

{% for article in articles[:10] %}
- [{{ article.title }}]({{ article.link }}) (q={{ "%.2f"|format(article.quality_score or 0) }})
{% endfor %}

{% endif %}
{% endfor %}
"""
