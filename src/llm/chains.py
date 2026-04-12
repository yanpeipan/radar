"""LangChain LCEL chains for report generation."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.llm.core import LLMClient, get_llm_client
from src.llm.output_models import (
    ClassifyTranslateOutput,
    TLDRItem,
)

# Default max tokens for LLM calls (chains can override via config dict)
DEFAULT_MAX_TOKENS = 300

# Per-chain max tokens overrides
MAX_TOKENS_PER_CHAIN: dict[str, int] = {
    "translate": 1000,  # full section translation
}


class JsonRegexOutputParser(Runnable):
    """Extract and parse JSON array from potentially mixed LLM output.

    Wraps the raw string and extracts JSON using regex, so the chain
    can handle cases where the LLM outputs text before/after the JSON.
    """

    def invoke(self, input: Any, config: Any = None) -> ClassifyTranslateOutput:
        raw = input if isinstance(input, str) else str(input)
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if json_match:
            parsed_dict = {"items": json.loads(json_match.group())}
        else:
            parsed_dict = {"items": []}
        return ClassifyTranslateOutput(**parsed_dict)

    async def ainvoke(self, input: Any, config: Any = None) -> ClassifyTranslateOutput:
        return self.invoke(input, config)


class TldrJsonOutputParser(Runnable):
    """Extract and parse TLDR JSON array from potentially mixed LLM output.

    Uses regex to extract JSON array from mixed text output, similar to
    JsonRegexOutputParser but returns list[TLDRItem].
    """

    def invoke(self, input: Any, config: Any = None) -> list[TLDRItem]:
        raw = input if isinstance(input, str) else str(input)
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if json_match:
            items_data = json.loads(json_match.group())
            return [TLDRItem(**item) for item in items_data]
        return []

    async def ainvoke(self, input: Any, config: Any = None) -> list[TLDRItem]:
        return self.invoke(input, config)


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
        if isinstance(input, ChatPromptValue):
            # LCEL prompt output — combine all messages into a single text prompt
            # Our LLMClient.complete() wraps a string prompt in {"role": "user", "content": prompt}
            parts = []
            for msg in input.messages:
                if hasattr(msg, "content") and msg.content:
                    parts.append(f"{msg.type.upper()}: {msg.content}")
            text = "\n".join(parts)
        elif isinstance(input, dict):
            # Try to extract text from dict input (LCEL passes prompt values as dicts)
            text = input.get("text", input.get("prompt", str(input)))
        elif isinstance(input, BaseMessage):
            text = input.content
        else:
            text = str(input)
        max_tokens = self._resolve_max_tokens(config)
        # Build extra_body from config first
        extra_body: dict[str, Any] = {}
        if isinstance(config, dict):
            extra_body = dict(config.get("extra_body", {}))
        # Then overlay instance-level settings (these MUST be applied)
        if self._response_format:
            extra_body["response_format"] = self._response_format
        if self._thinking:
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
_llm_wrapper_cache: dict[tuple[int, int | None, int | None], AsyncLLMWrapper] = {}


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
        id(response_format) if response_format else None,
        id(thinking) if thinking else None,
    )
    if key not in _llm_wrapper_cache:
        _llm_wrapper_cache[key] = AsyncLLMWrapper(
            max_tokens=max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
            response_format=response_format,
            thinking=thinking,
        )
    return _llm_wrapper_cache[key]


def _make_json_schema_response_format(schema: dict, name: str) -> dict:
    """Build response_format with json_schema + strict=True for MiniMax compatibility.

    LiteLLM expects: {"type": "json_schema", "json_schema": {"schema": {...}, "name": "...", "strict": true}}
    MiniMax only enforces JSON mode when strict=True is set.
    """
    return {
        "type": "json_schema",
        "json_schema": {"schema": schema, "name": name, "strict": True},
    }


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
        | _get_llm_wrapper(
            300,
            _make_json_schema_response_format(TLDRItem.model_json_schema(), "TLDRItem"),
        )
        | TldrJsonOutputParser()
    )


# Classification + translation chain
CLASSIFY_TRANSLATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional news tagging robot with CEO and news analyst judgment.",
        ),
        (
            "human",
            "Tag and translate news titles.\n\n"
            "Candidate tags:\n{tag_list}\n\n"
            "Rules:\n"
            "1. Each news item can have 0-3 tags, prefer the most specific.\n"
            "2. If no tags apply, tags = [].\n\n"
            "Output format:\n"
            'Return a JSON array, each element: {{"id": int, "tags": [], "translation": "..."}}\n\n'
            "News list:\n"
            "{news_list}\n\n"
            "Translate each title to {target_lang}.",
        ),
    ]
)


def get_classify_translate_chain(
    tag_list: str,
    news_list: str,
    target_lang: str = "zh",
) -> Runnable:
    """Returns LCEL chain for batch news classification and translation.

    Args:
        tag_list: Newline-separated candidate tags
        news_list: Newline-separated news titles (one per line)
        target_lang: Target language code (default: zh)
    """
    # JsonRegexOutputParser extracts JSON from mixed LLM output via regex,
    # so process_batch can use the parsed ClassifyTranslateOutput directly.
    return (
        CLASSIFY_TRANSLATE_PROMPT
        | _get_llm_wrapper(
            16384,
            _make_json_schema_response_format(
                ClassifyTranslateOutput.model_json_schema(), "ClassifyTranslateOutput"
            ),
        )
        | JsonRegexOutputParser()
    )
