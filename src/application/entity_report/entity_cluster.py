"""Layer 2: Entity clustering - group by normalized entity, classify dimension."""

import asyncio
from collections import defaultdict
from typing import Any

from .models import ArticleEnriched, EntityTag, EntityTopic


_DIMENSION_KEYWORDS = {
    "release": ["发布", "推出", "上线", "release", "launch", "debut", "unveil"],
    "funding": ["融资", "投资", "Funding", "Series", "investment", "raised", "round"],
    "research": ["研究", "论文", "发现", "research", "paper", "study", "discovery"],
    "ecosystem": ["生态", "合作", "集成", "partner", "ecosystem", "integration", "collab"],
    "policy": ["监管", "政策", "禁止", "regulation", "policy", "ban", "law", "EU AI Act"],
}


def _classify_dimension(text: str) -> str:
    """Classify article dimension from title+summary text using keyword matching."""
    text_lower = text.lower()
    scores: dict[str, int] = defaultdict(int)
    for dim, keywords in _DIMENSION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                scores[dim] += 1
    if scores:
        return max(scores, key=scores.get)  # type: ignore
    return "release"


async def _generate_entity_topic(
    entity: EntityTag,
    articles: list[ArticleEnriched],
    dimension: str,
) -> EntityTopic:
    """Generate headline and signals for an entity topic via LLM."""
    delays = [2, 4, 8]
    for attempt, delay in enumerate(delays):
        try:
            from src.llm.chains import get_entity_topic_chain

            chain = get_entity_topic_chain()
            titles = "\n".join(f"- {a.title}" for a in articles[:10])
            result = await chain.ainvoke(
                {
                    "entity": entity.name,
                    "titles": titles,
                    "dimension": dimension,
                }
            )
            parsed = result if isinstance(result, dict) else {}
            headline = parsed.get("headline", entity.name)
            signals = parsed.get("signals", [])
            return EntityTopic(
                entity=entity,
                articles=articles,
                dimension=dimension,
                headline=headline,
                signals=signals,
            )
        except Exception as e:
            if attempt < len(delays) - 1:
                await asyncio.sleep(delay)
            else:
                return EntityTopic(
                    entity=entity,
                    articles=articles,
                    dimension=dimension,
                    headline=entity.name,
                    signals=[],
                )
    # unreachable
    return EntityTopic(entity=entity, articles=articles, dimension=dimension)


class EntityClusterer:
    """Cluster articles by normalized entity and classify into 5 dimensions.

    Pipeline:
    1. Group articles by normalized entity_id
    2. Classify each cluster's dimension (release/funding/research/ecosystem/policy)
    3. For large clusters (>large_event_threshold articles), split by dimension
    4. Generate headline via LLM per cluster
    5. Rank by quality_weight and cap at TOP 50
    """

    def __init__(
        self,
        large_event_threshold: int = 50,
        top_n: int = 50,
    ) -> None:
        self.large_event_threshold = large_event_threshold
        self.top_n = top_n

    def _group_by_entity(
        self, articles: list[ArticleEnriched]
    ) -> dict[str, list[ArticleEnriched]]:
        """Group articles by their first entity's normalized_id."""
        groups: dict[str, list[ArticleEnriched]] = defaultdict(list)
        for article in articles:
            if article.entities:
                entity_id = article.entities[0].normalized_id
                groups[entity_id].append(article)
        return dict(groups)

    def _classify_dimension(self, articles: list[ArticleEnriched]) -> str:
        """Classify a cluster of articles into a dimension."""
        texts = " ".join(a.title + " " + (a.summary or "") for a in articles[:5])
        return _classify_dimension(texts)

    async def cluster(
        self, articles: list[ArticleEnriched]
    ) -> list[EntityTopic]:
        """Cluster enriched articles by entity, generate topics."""
        groups = self._group_by_entity(articles)
        topics: list[EntityTopic] = []

        for entity_id, arts in groups.items():
            dimension = self._classify_dimension(arts)
            entity_tag = arts[0].entities[0] if arts and arts[0].entities else EntityTag(
                name=entity_id, normalized_id=entity_id, type="UNKNOWN"
            )

            # Large event split: if > threshold, split by dimension
            if len(arts) > self.large_event_threshold:
                sub_groups: dict[str, list[ArticleEnriched]] = defaultdict(list)
                for a in arts:
                    dim = _classify_dimension(a.title + " " + (a.summary or ""))
                    sub_groups[dim].append(a)
                for dim, sub_arts in sub_groups.items():
                    topic = await _generate_entity_topic(entity_tag, sub_arts, dim)
                    topic.quality_weight = sum(
                        (a.quality_score or 0) * (a.feed_weight or 0) for a in sub_arts
                    ) / max(len(sub_arts), 1)
                    topics.append(topic)
            else:
                topic = await _generate_entity_topic(entity_tag, arts, dimension)
                topic.quality_weight = sum(
                    (a.quality_score or 0) * (a.feed_weight or 0) for a in arts
                ) / max(len(arts), 1)
                topics.append(topic)

        # Rank by quality_weight and cap
        topics.sort(key=lambda t: t.quality_weight, reverse=True)
        return topics[: self.top_n]
