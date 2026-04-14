"""Batch classification chain with LCEL Runnable interface."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable, RunnableLambda

from src.llm.output_models import ClassifyTranslateItem

if TYPE_CHECKING:
    from src.application.articles import ArticleListItem

from src.application.articles import ArticleListItem

logger = logging.getLogger(__name__)


def BatchClassifyChain(
    tag_list: str,
    target_lang: str,
    batch_size: int = 100,
    max_concurrency: int = 1,
) -> Runnable:
    """Factory: returns RunnableLambda that processes list[ArticleListItem] -> list[ArticleListItem].

    Batching: split input into batches of batch_size, process max_concurrency batches concurrently.
    Each batch calls get_classify_translate_chain, enriches articles in-place with .tags and .translation.
    """

    async def classify_fn(input: list[ArticleListItem]) -> list[ArticleListItem]:
        # Split input into batches
        batches = [
            (input[i : i + batch_size], i) for i in range(0, len(input), batch_size)
        ]
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_with_semaphore(
            batch_articles: list[ArticleListItem], batch_offset: int
        ) -> list[ClassifyTranslateItem]:
            async with semaphore:
                try:
                    # Build news_list and call chain
                    news_list = "\n".join(
                        f"{j + 1}. {art.title or ''}"
                        for j, art in enumerate(batch_articles)
                    )
                    from src.llm.chains import get_classify_translate_chain

                    chain = get_classify_translate_chain(
                        tag_list=tag_list,
                        news_list=news_list,
                        target_lang=target_lang,
                    )
                    output = await chain.ainvoke(
                        {
                            "tag_list": tag_list,
                            "news_list": news_list,
                            "target_lang": target_lang,
                        }
                    )
                    # Adjust IDs for batch offset
                    for item in output.items:
                        item.id += batch_offset
                    return output.items
                except Exception as e:
                    logger.warning("Batch %d failed: %s", batch_offset, e)
                    return []

        batch_results = await asyncio.gather(
            *[run_with_semaphore(arts, offset) for arts, offset in batches]
        )

        # Flatten and build lookup dicts
        all_items: list[ClassifyTranslateItem] = []
        for batch_items in batch_results:
            all_items.extend(batch_items)

        trans_by_id = {item.id: item.translation for item in all_items}
        tags_by_id = {item.id: item.tags for item in all_items}

        # Enrich original articles in-place
        for idx, art in enumerate(input, 1):
            art.tags = tags_by_id.get(idx, [])
            art.translation = trans_by_id.get(idx)

        return input

    return RunnableLambda(classify_fn)
