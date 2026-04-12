"""Batch classification chain with LCEL Runnable interface."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.runnables import Runnable

from src.llm.output_models import ClassifyTranslateItem

if TYPE_CHECKING:
    from src.application.articles import ArticleListItem
    from src.application.report.template import HeadingNode

from src.application.articles import ArticleListItem

logger = logging.getLogger(__name__)


class ReportDataAdapter(Runnable):
    """Adapter that captures HeadingNode and passes it with articles as tuple.

    Bridges: BatchClassifyChain (list[ArticleListItem]) -> BuildReportDataChain (tuple[list, HeadingNode])
    """

    def __init__(self, heading_tree: "HeadingNode | None") -> None:
        self.heading_tree = heading_tree

    async def ainvoke(
        self, input: list[ArticleListItem], config=None
    ) -> tuple[list[ArticleListItem], "HeadingNode | None"]:
        return (input, self.heading_tree)

    def invoke(
        self, input: list[ArticleListItem], config=None
    ) -> tuple[list[ArticleListItem], "HeadingNode | None"]:
        return (input, self.heading_tree)


class BatchClassifyChain(Runnable):
    """Input list[ArticleListItem], internal batching, output list[ClassifyTranslateItem].

    Wraps get_classify_translate_chain with batching, semaphore-based concurrency,
    and silent error handling.
    """

    def __init__(
        self,
        tag_list: str,
        target_lang: str,
        batch_size: int = 50,
        max_concurrency: int = 5,
    ) -> None:
        self.tag_list = tag_list
        self.target_lang = target_lang
        self.batch_size = batch_size
        self.max_concurrency = max_concurrency

    def _build_news_list(self, batch_articles: list[ArticleListItem]) -> str:
        """Build 1-indexed news list string for LLM prompt."""
        return "\n".join(
            f"{i + 1}. {art.title or ''}" for i, art in enumerate(batch_articles)
        )

    async def _run_single_batch(
        self,
        batch_articles: list[ArticleListItem],
        batch_offset: int,
    ) -> list[ClassifyTranslateItem]:
        """Run a single batch through get_classify_translate_chain."""
        from src.llm.chains import get_classify_translate_chain

        news_list = self._build_news_list(batch_articles)
        chain = get_classify_translate_chain(
            tag_list=self.tag_list,
            news_list=news_list,
            target_lang=self.target_lang,
        )
        output = await chain.ainvoke(
            {
                "tag_list": self.tag_list,
                "news_list": news_list,
                "target_lang": self.target_lang,
            }
        )
        for item in output.items:
            item.id += batch_offset
        return output.items

    async def ainvoke(
        self,
        input: list[ArticleListItem],
        config=None,
    ) -> list[ArticleListItem]:
        """Main entry: split input into batches, process concurrently with semaphore.

        Returns list[ArticleListItem] with .tags and .translation populated from LLM output.
        """
        # Split input into batches
        batches = []
        for i in range(0, len(input), self.batch_size):
            batch_articles = input[i : i + self.batch_size]
            batches.append((batch_articles, i))  # (articles, offset)

        # Create semaphore at outer level (not in abatch)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def run_with_semaphore(
            batch_articles: list[ArticleListItem], batch_offset: int
        ) -> list[ClassifyTranslateItem]:
            async with semaphore:
                try:
                    return await self._run_single_batch(batch_articles, batch_offset)
                except Exception as e:
                    logger.warning(
                        "Batch %d failed: %s — returning empty list",
                        batch_offset,
                        e,
                    )
                    return []

        # Run all batches concurrently
        batch_results = await asyncio.gather(
            *[run_with_semaphore(arts, offset) for arts, offset in batches]
        )

        # Flatten results into single list
        all_items: list[ClassifyTranslateItem] = []
        for batch_items in batch_results:
            all_items.extend(batch_items)

        # Build lookup dicts from LLM output
        trans_by_id = {item.id: item.translation for item in all_items}
        tags_by_id = {item.id: item.tags for item in all_items}

        # Enrich original ArticleListItem objects in-place
        for idx, art in enumerate(input, 1):
            art.tags = tags_by_id.get(idx, [])
            art.translation = trans_by_id.get(idx)

        return input

    def invoke(
        self,
        input: list[ArticleListItem],
        config=None,
    ) -> list[ArticleListItem]:
        """Sync wrapper using new_event_loop pattern."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.ainvoke(input, config))
        finally:
            loop.close()

    async def abatch(
        self,
        inputs: list[list[ArticleListItem]],
        config=None,
    ) -> list[list[ArticleListItem]]:
        """Process multiple article lists as separate batches (LCEL convention)."""
        return [await self.ainvoke(inp, config) for inp in inputs]

    def batch(
        self,
        inputs: list[list[ArticleListItem]],
        config=None,
    ) -> list[list[ArticleListItem]]:
        """Sync wrapper for abatch."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.abatch(inputs, config))
        finally:
            loop.close()
