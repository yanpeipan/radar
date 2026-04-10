"""Layer 3: TLDR generator - top-10 TLDR summary via single LLM call."""

import asyncio

from .models import EntityTopic


class TLDRGenerator:
    """Generate a Today's Top 10 TLDR summary from top-ranked entity topics.

    Design:
    - Takes top N topics ranked by quality_weight
    - Single LLM call to generate TLDR list
    - Retry with 2s/4s/8s backoff, fallback to empty list
    """

    def __init__(self, top_n: int = 10) -> None:
        self.top_n = top_n

    async def generate_top10(
        self, topics: list[EntityTopic], target_lang: str = "zh"
    ) -> list[str]:
        """Generate TLDR list for top-ranked entity topics.

        Args:
            topics: List of EntityTopic sorted by quality_weight (descending).
            target_lang: Target language code (zh, en, ja, ko).

        Returns:
            List of TLDR strings, one per topic (max top_n).
        """
        if not topics:
            return []

        selected = topics[: self.top_n]
        delays = [2, 4, 8]
        for attempt, delay in enumerate(delays):
            try:
                from src.llm.chains import get_tldr_chain

                chain = get_tldr_chain()
                lines = []
                for i, topic in enumerate(selected, 1):
                    headline = topic.headline or topic.entity.name
                    articles_text = " | ".join(
                        a.title for a in topic.articles[:3]
                    )
                    lines.append(f"{i}. [{topic.dimension}] {headline}: {articles_text}")

                prompt_text = "\n".join(lines)
                lang_name = {"zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어"}.get(
                    target_lang, "English"
                )
                result = await chain.ainvoke(
                    {"topics": prompt_text, "target_lang": lang_name}
                )
                parsed = result if isinstance(result, list) else []
                return [str(item) for item in parsed]
            except Exception as e:
                if attempt < len(delays) - 1:
                    await asyncio.sleep(delay)
                else:
                    # Fallback: return entity headlines as-is
                    return [
                        f"[{t.dimension}] {t.headline or t.entity.name}"
                        for t in selected
                    ]
        return []
