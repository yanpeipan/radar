"""Layer 4: Render — entity report Jinja2 rendering."""

from __future__ import annotations

from typing import Any

def group_by_layer(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        layer = getattr(t, "layer", "AI应用")
        result.setdefault(layer, []).append(t)
    return result


def group_by_dimension(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        tags = getattr(t, "tags", [])
        for tag in tags:
            result.setdefault(tag.name, []).append(t)
    return result


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
    try:
        template = env.get_template(f"{template_name}.md")
    except Exception:
        raise

    by_layer = group_by_layer(entity_topics)
    by_dimension = group_by_dimension(entity_topics)
    deep_dive = [t for t in entity_topics if len(getattr(t, "children", [])) > 50]

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
    )
