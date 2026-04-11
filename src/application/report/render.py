"""Layer 4: Render — entity report Jinja2 rendering."""

from __future__ import annotations

from typing import Any

# Dimension translation
DIM_ZH: dict[str, str] = {
    "release": "发布",
    "funding": "融资",
    "research": "研究",
    "ecosystem": "生态",
    "policy": "监管",
}


def dim_zh(dim: str) -> str:
    """Translate dimension key to Chinese."""
    return DIM_ZH.get(dim, dim)


def group_by_layer(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        layer = getattr(t, "layer", "AI应用")
        result.setdefault(layer, []).append(t)
    return result


def group_by_dimension(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        for dim in getattr(t, "dimensions", {}):
            result.setdefault(dim, []).append(t)
    return result


def _sum_articles(topics: list) -> int:
    return sum(getattr(t, "articles_count", 0) for t in topics)


def _topic_sort_key(t: Any) -> float:
    return getattr(t, "quality_weight", 0.0)


async def render_report(
    entity_topics: list,
    since: str,
    until: str,
    target_lang: str,
    template_name: str = "entity",
) -> str:
    """Render entity report using Jinja2.

    Falls back to inline rendering if template not found.
    """
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_dirs = [
        Path.home() / ".local" / "share" / "feedship" / "templates",
        Path(__file__).parent.parent.parent.parent / "templates",
    ]
    env = Environment(
        loader=FileSystemLoader([str(d) for d in template_dirs]),
        autoescape=select_autoescape(),
    )
    env.filters["dim_zh"] = dim_zh
    env.globals["sum_articles"] = _sum_articles

    try:
        template = env.get_template(f"{template_name}.md")
    except Exception:
        return render_entity_inline(entity_topics, since, until, target_lang)

    by_layer = group_by_layer(entity_topics)
    by_dimension = group_by_dimension(entity_topics)
    deep_dive = [t for t in entity_topics if getattr(t, "articles_count", 0) > 50]

    for layer_list in by_layer.values():
        layer_list.sort(key=_topic_sort_key, reverse=True)
    for dim_list in by_dimension.values():
        dim_list.sort(key=_topic_sort_key, reverse=True)
    deep_dive.sort(key=_topic_sort_key, reverse=True)

    return template.render(
        tldr_top10=entity_topics[:10],
        by_layer=by_layer,
        by_dimension=by_dimension,
        deep_dive=deep_dive,
        date_range={"since": since, "until": until},
        target_lang=target_lang,
        dim_zh=dim_zh,
    )


def render_entity_inline(
    entity_topics: list,
    since: str,
    until: str,
    target_lang: str,
) -> str:
    """Inline markdown rendering fallback when template not available."""
    by_layer = group_by_layer(entity_topics)
    lines = [
        f"# AI Daily Report — {since} to {until}",
        "",
        "## Today's Top 10 AI News",
    ]
    for i, topic in enumerate(entity_topics[:10]):
        lines.append(f"{i + 1}. **{topic.headline}** [{topic.articles_count} articles]")
        if topic.tldr:
            lines.append(f"   {topic.tldr}")
        lines.append("")

    lines.append("## By Layer")
    for layer, topics in by_layer.items():
        article_count = sum(t.articles_count for t in topics)
        lines.append(f"### {layer} ({article_count} articles, {len(topics)} topics)")
        for topic in topics[:5]:
            lines.append(f"#### {topic.entity_name} ({topic.articles_count} articles)")
            lines.append(f"{topic.headline}")
            if topic.tldr:
                lines.append(f"_{topic.tldr}_")
            lines.append(f"Signals: {', '.join(topic.signals)}")
            lines.append("")

    return "\n".join(lines)
