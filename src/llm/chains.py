"""LangChain LCEL chains for report generation."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.llm.core import LLMClient, get_llm_client


class AsyncLLMWrapper(Runnable):
    """LCEL Runnable that delegates to LLMClient.complete().

    Provides provider fallback + rate-limiting for LCEL chains.
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._client = llm_client

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = get_llm_client()
        return self._client

    async def _ainvoke_raw(self, input: Any) -> str:
        """Invoke with raw string input (for use with StrOutputParser)."""
        if isinstance(input, dict):
            # Try to extract text from dict input (LCEL passes prompt values as dicts)
            # When used as: prompt | model | parser, the prompt outputs a string
            # But some chains pass dicts, so handle both cases
            text = input.get("text", input.get("prompt", str(input)))
        elif isinstance(input, BaseMessage):
            text = input.content
        else:
            text = str(input)
        return await self.client.complete(text)

    async def ainvoke(
        self,
        input: Any,
        config: Any = None,
        **kwargs: Any,
    ) -> str:
        """Async invoke — compatible with LCEL chain."""
        return await self._ainvoke_raw(input)

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> str:
        """Sync invoke — delegates to async version via thread pool."""
        import asyncio
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, self._ainvoke_raw(input))
            return future.result()

    async def abatch(
        self,
        inputs: list[Any],
        **kwargs: Any,
    ) -> list[str]:
        """Async batch invoke."""
        return [await self._ainvoke_raw(i) for i in inputs]

    def batch(self, inputs: list[Any], **kwargs: Any) -> list[str]:
        """Sync batch invoke."""
        return [self.invoke(i) for i in inputs]


# Singleton wrapper instance
_async_llm_wrapper: AsyncLLMWrapper | None = None


def _get_llm_wrapper() -> AsyncLLMWrapper:
    """Get or create the singleton AsyncLLMWrapper."""
    global _async_llm_wrapper
    if _async_llm_wrapper is None:
        _async_llm_wrapper = AsyncLLMWrapper()
    return _async_llm_wrapper


# Article classification chain using LCEL
CLASSIFY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Classify this article into ONE of the following categories:
- AI应用 (Application): AI products, tools, and services used by end users
- AI模型 (Model): AI model releases, benchmarks, research papers, training methods
- AI基础设施 (Infrastructure): Cloud platforms, MLOps tools, deployment, APIs
- 芯片 (Chip): AI hardware, GPUs, custom silicon, semiconductor news (e.g., NVIDIA Blackwell, Groq, Cerebras, TSMC, AMD GPU)
- 能源 (Energy): AI energy consumption, data center power, carbon footprint, renewable energy for AI""",
        ),
        (
            "human",
            "Article Title: {title}\nArticle Content: {content}\n\nReturn ONLY the category name.",
        ),
    ]
)


def get_classify_chain():
    """Returns LCEL chain for article classification."""
    return CLASSIFY_PROMPT | _get_llm_wrapper() | StrOutputParser()


# Layer summary generation chain
LAYER_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You are writing a concise summary for a news report section."),
        (
            "human",
            """The following articles are about: {layer}

Articles:
{article_list}

Write 2-3 paragraphs summarizing the key trends and insights from these articles.
Focus on the most important developments. Use professional Chinese.

Summary:""",
        ),
    ]
)


def get_layer_summary_chain():
    """Returns LCEL chain for layer summary generation."""
    return LAYER_SUMMARY_PROMPT | _get_llm_wrapper() | StrOutputParser()


# Report quality evaluation chain
EVALUATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional news report editor. Evaluate report quality objectively. Return ONLY valid JSON.",
        ),
        (
            "human",
            """Evaluate this daily report and score each dimension 0.0-1.0.

Report:
{report}

Return ONLY valid JSON with four scores: coherence (0.0-1.0), relevance (0.0-1.0), depth (0.0-1.0), structure (0.0-1.0). Example: {"coherence": 0.8, "relevance": 0.7, "depth": 0.6, "structure": 0.9}""",
        ),
    ]
)


def get_evaluate_chain():
    """Returns LCEL chain for report quality evaluation."""
    return EVALUATE_PROMPT | _get_llm_wrapper() | StrOutputParser()


# Translation chain
TRANSLATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional translator. Translate the following text to {target_lang}. Preserve all markdown formatting, bullet points, and links. Do NOT translate article titles, proper nouns, or content inside [text](url) link patterns.",
        ),
        (
            "human",
            "Text to translate:\n{text}",
        ),
    ]
)


def get_translate_chain():
    """Returns LCEL chain for report translation."""
    return TRANSLATE_PROMPT | _get_llm_wrapper() | StrOutputParser()
