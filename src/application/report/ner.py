"""Layer 1: NER + Entity Resolution — extract and normalize entities from articles."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from src.application.report.models import ArticleEnriched, EntityTag
from src.llm.chains import get_ner_chain


def normalize_entity(name: str, _type: str | None = None) -> str:
    """Normalize entity name to lowercase underscore slug.

    Examples:
        "Google Gemma 4" -> "google_gemma_4"
        "gemma-4" -> "gemma_4"
        "OpenAI" -> "openai"
        "Sam Altman" -> "sam_altman"
    """
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s-]+", "_", s)
    return s


class NERExtractor:
    """Extract named entities from articles using LLM batch processing."""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    async def extract_batch(
        self, articles: list[dict[str, Any]]
    ) -> list[ArticleEnriched]:
        """Process articles in batches. Returns enriched articles with entity tags."""
        import json as json_mod

        chain = get_ner_chain()
        results: list[ArticleEnriched] = []
        semaphore = asyncio.Semaphore(3)

        async def process_batch(batch: list[dict[str, Any]]) -> list[ArticleEnriched]:
            async with semaphore:
                articles_block = "\n".join(
                    f"Article {i + 1} (id={a['id']}): {a.get('title', '')[:200]}"
                    for i, a in enumerate(batch)
                )
                try:
                    raw = await chain.ainvoke({"articles_block": articles_block})
                    parsed = json_mod.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    return [
                        ArticleEnriched(
                            id=a["id"],
                            title=a.get("title", ""),
                            link=a.get("link", ""),
                            summary=a.get("summary", ""),
                            quality_score=a.get("quality_score", 0.0),
                            feed_weight=a.get("feed_weight", 0.0),
                            published_at=a.get("published_at", ""),
                            feed_id=a.get("feed_id", "unknown"),
                            entities=[],
                            dimensions=[],
                        )
                        for a in batch
                    ]

            id_to_entities: dict[str, list[EntityTag]] = {}
            for item in parsed:
                aid = item.get("id", "")
                id_to_entities[aid] = [
                    EntityTag(
                        name=e["name"],
                        type=e.get("type", "ORG"),
                        normalized=normalize_entity(e["name"], e.get("type")),
                    )
                    for e in item.get("entities", [])
                ]

            enriched = []
            for a in batch:
                entities = id_to_entities.get(a["id"], [])
                enriched.append(
                    ArticleEnriched(
                        id=a["id"],
                        title=a.get("title", ""),
                        link=a.get("link", ""),
                        summary=a.get("summary", ""),
                        quality_score=a.get("quality_score", 0.0),
                        feed_weight=a.get("feed_weight", 0.0),
                        published_at=a.get("published_at", ""),
                        feed_id=a.get("feed_id", "unknown"),
                        entities=entities,
                        dimensions=[],
                    )
                )
            return enriched

        batches = [
            articles[i : i + self.batch_size]
            for i in range(0, len(articles), self.batch_size)
        ]
        batch_results = await asyncio.gather(*[process_batch(b) for b in batches])
        for batch_result in batch_results:
            results.extend(batch_result)
        return results
