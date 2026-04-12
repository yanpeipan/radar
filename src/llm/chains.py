"""LangChain LCEL chains for report generation."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.llm.core import _get_llm_wrapper
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
        # Handle AIMessage with content as list (when model returns structured output with thinking)
        if hasattr(input, "content") and isinstance(input.content, list):
            text_parts = []
            for item in input.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            raw = "\n".join(text_parts)
        else:
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
        # Handle AIMessage with content as list (when model returns structured output with thinking)
        if hasattr(input, "content") and isinstance(input.content, list):
            # Extract text from content list (handles thinking + text structure)
            text_parts = []
            for item in input.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "thinking":
                        pass  # Skip thinking blocks
            raw = "\n".join(text_parts)
        else:
            raw = input if isinstance(input, str) else str(input)
        json_match = re.search(r"\[.*\]", raw, re.DOTALL)
        if json_match:
            try:
                items_data = json.loads(json_match.group())
                return [TLDRItem(**item) for item in items_data]
            except Exception:
                pass
        return []

    async def ainvoke(self, input: Any, config: Any = None) -> list[TLDRItem]:
        return self.invoke(input, config)


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


# TLDR chain — generate detailed TLDR for multiple entities at once
TLDR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior news analyst with CEO + AI/Technology analyst dual perspectives.\n"
            "Each entity topic has multiple related articles discussing the same subject.\n"
            "Synthesize ALL articles to write a deep, insightful 2-3 sentence summary.\n\n"
            "Your analysis should:\n"
            "1. CEO视角: business impact, strategic implications, market significance\n"
            "2. AI Analyst视角: technical innovations, AI/ML trends, industry breakthroughs\n\n"
            "Write in {target_lang}.",
        ),
        (
            "human",
            "Entity Topics (top {top_n} articles each, multiple perspectives per topic):\n"
            "{article_titles}\n\n"
            'Return JSON array of {{"entity_id": "...", "tldr": "..."}} for each topic.',
        ),
    ]
)


def get_tldr_chain() -> Runnable:
    """Returns LCEL chain for batch TLDR generation."""
    return TLDR_PROMPT | _get_llm_wrapper(800) | TldrJsonOutputParser()


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
