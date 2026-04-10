"""Layer 3: TLDR Generation — 1-sentence TLDR for top 10 entities."""

from __future__ import annotations

from src.application.report.models import EntityTopic
from src.llm.chains import get_tldr_chain


class TLDRGenerator:
    def __init__(self, top_n: int = 10):
        self.top_n = top_n

    async def generate_top10(
        self, entity_topics: list[EntityTopic], target_lang: str
    ) -> list[EntityTopic]:
        """Take top N by quality_weight, generate tldr in-place. Returns top N."""
        import json as json_mod

        sorted_topics = sorted(
            entity_topics, key=lambda t: t.quality_weight, reverse=True
        )[: self.top_n]

        if not sorted_topics:
            return []

        topics_block = "\n".join(
            f"Entity {i + 1} ({t.entity_name}): {t.headline}"
            for i, t in enumerate(sorted_topics)
        )

        chain = get_tldr_chain()
        try:
            raw = await chain.ainvoke(
                {
                    "topics_block": topics_block,
                    "target_lang": target_lang,
                }
            )
            parsed = json_mod.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return sorted_topics

        tldr_map = {item.get("entity_id", ""): item.get("tldr", "") for item in parsed}
        for topic in sorted_topics:
            topic.tldr = tldr_map.get(topic.entity_id, "")

        return sorted_topics
