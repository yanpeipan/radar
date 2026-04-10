"""Layer 2: Entity Clustering — group articles by entity, classify dimensions."""

from __future__ import annotations

import asyncio

from src.application.report.models import ArticleEnriched, EntityTopic
from src.llm.chains import get_entity_topic_chain

# Dimension keywords for rule-based classification
_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "release": ["release", "launch", "announce", "发布", "推出", "launches", "unveils"],
    "funding": ["funding", "raise", "series", "vc", "invest", "融资", "投资", "raises"],
    "research": ["research", "paper", "study", "benchmark", "研究", "论文", "arxiv"],
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

# Five layers
_LAYERS = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"]


def classify_dimensions(article: ArticleEnriched) -> list[str]:
    """Classify article into one or more dimensions by keyword matching."""
    text = (article.title + " " + article.summary).lower()
    dims = []
    for dim, keywords in _DIMENSION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            dims.append(dim)
    return dims if dims else ["ecosystem"]


class EntityClusterer:
    """Cluster articles by entity and generate entity topics."""

    def __init__(
        self,
        large_event_threshold: int = 50,
        max_entities: int = 50,
    ):
        self.large_event_threshold = large_event_threshold
        self.max_entities = max_entities

    async def cluster(
        self, articles: list[ArticleEnriched], target_lang: str
    ) -> list[EntityTopic]:
        """Main entry: articles -> entity topics."""
        # Group by normalized entity
        entity_groups: dict[str, list[ArticleEnriched]] = {}
        for article in articles:
            if not article.entities:
                feed_id = article.feed_id or "unknown"
                entity_groups.setdefault(feed_id, []).append(article)
            else:
                primary = article.entities[0].normalized
                entity_groups.setdefault(primary, []).append(article)

        # Rank by quality_weight and take top max_entities
        ranked = sorted(
            entity_groups.items(),
            key=lambda x: sum(a.quality_score for a in x[1]) * len(x[1]),
            reverse=True,
        )
        ranked = ranked[: self.max_entities]

        # Generate topic for each entity
        chain = get_entity_topic_chain()
        semaphore = asyncio.Semaphore(5)
        topics: list[EntityTopic] = []

        async def generate_one(
            entity_id: str, entity_articles: list[ArticleEnriched]
        ) -> EntityTopic | None:
            async with semaphore:
                for art in entity_articles:
                    art.dimensions = classify_dimensions(art)

                by_dim: dict[str, list[ArticleEnriched]] = {}
                for art in entity_articles:
                    for dim in art.dimensions:
                        by_dim.setdefault(dim, []).append(art)

                article_list = "\n".join(
                    f"- [{a.title}]({a.link})" for a in entity_articles[:10]
                )
                entity_name = (
                    entity_articles[0].entities[0].name
                    if entity_articles[0].entities
                    else entity_id
                )

                try:
                    result = await chain.ainvoke(
                        {
                            "entity_name": entity_name,
                            "article_count": len(entity_articles),
                            "article_list": article_list,
                            "target_lang": target_lang,
                        }
                    )
                except Exception:
                    return EntityTopic(
                        entity_id=entity_id,
                        entity_name=entity_name,
                        layer="AI应用",
                        headline=entity_name[:30],
                        dimensions=by_dim,
                        articles_count=len(entity_articles),
                        signals=[],
                        tldr="",
                        quality_weight=sum(a.quality_score for a in entity_articles)
                        * len(entity_articles),
                    )

                layer = result.get("layer", "AI应用")
                if layer not in _LAYERS:
                    layer = "AI应用"

                return EntityTopic(
                    entity_id=entity_id,
                    entity_name=entity_name,
                    layer=layer,
                    headline=result.get("headline", entity_name[:30]),
                    dimensions=by_dim,
                    articles_count=len(entity_articles),
                    signals=result.get("signals", []),
                    tldr="",
                    quality_weight=sum(a.quality_score for a in entity_articles)
                    * len(entity_articles),
                )

        results = await asyncio.gather(
            *[generate_one(eid, earts) for eid, earts in ranked]
        )
        topics = [r for r in results if r is not None]
        return topics
