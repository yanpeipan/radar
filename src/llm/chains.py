"""LangChain LCEL chains for report generation."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.llm.core import LLMClient, get_llm_client

# Default max tokens for LLM calls (chains can override via config dict)
DEFAULT_MAX_TOKENS = 300

# Per-chain max tokens overrides
MAX_TOKENS_PER_CHAIN: dict[str, int] = {
    "evaluate": 200,  # JSON with 4 scores
    "translate": 1000,  # full section translation
}


class AsyncLLMWrapper(Runnable):
    """LCEL Runnable that delegates to LLMClient.complete().

    Provides provider fallback + rate-limiting for LCEL chains.
    Supports per-chain max_tokens via config dict: {"max_tokens": N, "chain_name": "..."}
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        response_format: dict | None = None,
        thinking: dict | None = None,
    ) -> None:
        self._client = llm_client
        self._max_tokens = max_tokens
        self._response_format = response_format
        self._thinking = thinking

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = get_llm_client()
        return self._client

    def _resolve_max_tokens(self, config: Any) -> int:
        """Resolve max_tokens from config dict or use instance default."""
        if isinstance(config, dict):
            return config.get("max_tokens", self._max_tokens)
        return self._max_tokens

    async def _ainvoke_raw(self, input: Any, config: Any = None) -> str:
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
        max_tokens = self._resolve_max_tokens(config)
        extra_body = {}
        if isinstance(config, dict):
            extra_body = config.get("extra_body", {})
        if self._response_format:
            extra_body = dict(extra_body)
            extra_body["response_format"] = self._response_format
        if self._thinking:
            extra_body = dict(extra_body)
            extra_body["thinking"] = self._thinking
        return await self.client.complete(
            text, max_tokens=max_tokens, extra_body=extra_body
        )

    async def ainvoke(
        self,
        input: Any,
        config: Any = None,
        **kwargs: Any,
    ) -> str:
        """Async invoke — compatible with LCEL chain."""
        return await self._ainvoke_raw(input, config)

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> str:
        """Sync invoke — uses new event loop per call to avoid loop-in-loop crashes.

        Uses asyncio.new_event_loop() + run_until_complete() instead of asyncio.run()
        to avoid 'RuntimeError: asyncio.run() cannot be called from a running event loop'.
        Each call creates and closes its own loop, which is safe for sync contexts.
        """
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._ainvoke_raw(input, config))
        finally:
            loop.close()

    async def abatch(
        self,
        inputs: list[Any],
        config: Any = None,
        **kwargs: Any,
    ) -> list[str]:
        """Async batch invoke."""
        return [await self._ainvoke_raw(i, config) for i in inputs]

    def batch(
        self,
        inputs: list[Any],
        config: Any = None,
        **kwargs: Any,
    ) -> list[str]:
        """Sync batch invoke."""
        return [self.invoke(i, config) for i in inputs]


# Cache of wrappers per (max_tokens, response_format, thinking) to avoid per-call instantiation
_llm_wrapper_cache: dict[tuple[int, frozenset[tuple[str, Any]], frozenset[tuple[str, Any]]], AsyncLLMWrapper] = {}


def _get_llm_wrapper(
    max_tokens: int | None = None,
    response_format: dict | None = None,
    thinking: dict | None = None,
) -> AsyncLLMWrapper:
    """Get or create a cached AsyncLLMWrapper.

    Using a cache avoids creating a new LLM client per chain call while
    supporting per-chain max_tokens overrides, JSON mode via response_format,
    and thinking config.
    """
    key = (
        max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        frozenset(response_format.items()) if response_format else frozenset(),
        frozenset(thinking.items()) if thinking else frozenset(),
    )
    if key not in _llm_wrapper_cache:
        _llm_wrapper_cache[key] = AsyncLLMWrapper(
            max_tokens=key[0],
            response_format=response_format,
            thinking=thinking,
        )
    return _llm_wrapper_cache[key]


# Report quality evaluation chain
EVALUATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional news report editor. Evaluate report quality objectively.",
        ),
        (
            "human",
            """Evaluate this daily report and score each dimension 0.0-1.0.

Report:
{report}

Return ONLY valid JSON with four scores: coherence (0.0-1.0), relevance (0.0-1.0), depth (0.0-1.0), structure (0.0-1.0). Example: {{"coherence": 0.8, "relevance": 0.7, "depth": 0.6, "structure": 0.9}}""",
        ),
    ]
)


def get_evaluate_chain() -> Runnable:
    """Returns LCEL chain for report quality evaluation."""
    return (
        EVALUATE_PROMPT
        | _get_llm_wrapper(MAX_TOKENS_PER_CHAIN["evaluate"], {"type": "json_object"})
        | JsonOutputParser()
    )


# Translation chain — for section summaries, preserves article titles in links
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


def get_translate_chain() -> Runnable:
    """Returns LCEL chain for report section translation."""
    return (
        TRANSLATE_PROMPT
        | _get_llm_wrapper(MAX_TOKENS_PER_CHAIN["translate"])
        | StrOutputParser()
    )


# NER chain — batch extract named entities from articles
NER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a named entity recognition system. Extract entities from articles.",
        ),
        (
            "human",
            "Articles:\n{articles_block}\n\n"
            'Return JSON array of {{"id": "article_id", "entities": [{{"name": "...", "type": "ORG|PRODUCT|MODEL|PERSON|EVENT", "normalized": "..."}}]}} for each article.',
        ),
    ]
)


def get_ner_chain() -> Runnable:
    """Returns LCEL chain for batch NER extraction."""
    return (
        NER_PROMPT
        | _get_llm_wrapper(200, {"type": "json_object"}, {"type": "disabled"})
        | JsonOutputParser()
    )


# Entity topic chain — headline + layer + signals for one entity
ENTITY_TOPIC_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a news analyst. For the given entity and its articles, "
            "generate: (1) a headline (max 30 chars), (2) the AI five-layer cake layer, "
            "(3) signal tags, (4) a 1-sentence insight. "
            "Layers: AI应用, AI模型, AI基础设施, 芯片, 能源.",
        ),
        (
            "human",
            "Entity: {entity_name}\nArticles ({article_count}):\n{article_list}\n\n"
            "Return JSON with: headline, layer, signals (list), insight.",
        ),
    ]
)


def get_entity_topic_chain() -> Runnable:
    """Returns LCEL chain for entity topic headline + layer + signals."""
    return (
        ENTITY_TOPIC_PROMPT
        | _get_llm_wrapper(150, {"type": "json_object"})
        | JsonOutputParser()
    )


# TLDR chain — generate 1-sentence TLDR for multiple entities at once
TLDR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a news editor. Generate a 1-sentence TLDR for each entity topic. "
            "Focus on: what happened, why it matters. Write in {target_lang}.",
        ),
        (
            "human",
            "Entity Topics:\n{topics_block}\n\n"
            'Return JSON array of {{"entity_id": "...", "tldr": "..."}} for each topic.',
        ),
    ]
)


def get_tldr_chain() -> Runnable:
    """Returns LCEL chain for batch TLDR generation."""
    return (
        TLDR_PROMPT
        | _get_llm_wrapper(300, {"type": "json_object"})
        | JsonOutputParser()
    )
