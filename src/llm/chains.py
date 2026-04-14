"""LangChain LCEL chains for report generation."""

from __future__ import annotations

import json

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.llm.core import LLMWrapper
from src.llm.output_models import (
    ClassifyTranslateOutput,
    TopicInsightOutput,
)

# ---------------------------------------------------------------------------
# Wrapper schemas for list outputs (required for .with_structured_output())
# ---------------------------------------------------------------------------


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
    return TRANSLATE_PROMPT | LLMWrapper() | StrOutputParser()


# Classification + translation chain
CLASSIFY_TRANSLATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional news tagging robot with CEO and news analyst judgment.\n"
            "Output ONLY valid JSON. Example format:\n"
            '{{"items": [{{"id": 1, "tags": ["AI"], "translation": "title"}}]}}\n'
            "The 'items' value must be a JSON array, NOT a quoted string.",
        ),
        (
            "human",
            "Tag and translate news titles to {target_lang}.\n\n"
            "Candidate tags:\n{tag_list}\n\n"
            "Rules:\n"
            "1. Each news item can have 1-3 tags, prefer the most specific.\n"
            "2. If no tags apply, DO NOT include this item in the output.\n"
            "3. Output JSON with 'items' as a proper array (not a string).\n\n"
            "News list:\n"
            "{news_list}",
        ),
    ]
)


def _parse_classify_output(text: str) -> ClassifyTranslateOutput:
    """Parse LLM output, handling double-encoded JSON strings from MiniMax API.

    MiniMax sometimes double-encodes the JSON array as a string within the
    ClassifyTranslateOutput model. This parser catches that case.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try parsing as-is if not a JSON string
        raise ValueError(f"Invalid JSON: {text[:200]}") from None

    # MiniMax double-encodes: items is a JSON string instead of array
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], str):
        data["items"] = json.loads(data["items"])

    return ClassifyTranslateOutput.model_validate(data)


def get_classify_translate_chain(
    tag_list: str,
    news_list: str,
    target_lang: str = "zh",
) -> Runnable:
    """Returns LCEL chain for batch news classification and translation."""
    return (
        CLASSIFY_TRANSLATE_PROMPT
        | LLMWrapper()
        | StrOutputParser()
        | _parse_classify_output
    )


# ---------------------------------------------------------------------------
# InsightChain chains — generate cluster.summary and cluster.children (Topics)
# ---------------------------------------------------------------------------

# Insight chain — generate topics with insights for rich clusters (>= 2 articles)
INSIGHT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior news analyst with CEO + AI/Technology analyst dual perspectives.\n"
            "Each cluster has multiple related articles on the same subject.\n"
            "Generate TOPICS worth deep-diving (only if 2+ articles can be synthesized).\n"
            "Write in {target_lang}.",
        ),
        (
            "human",
            "Cluster articles (top {top_n}):\n{article_titles}",
        ),
    ]
)


def get_insight_chain() -> Runnable:
    """Returns LCEL chain for batch topic insight generation."""
    return INSIGHT_PROMPT | LLMWrapper(structured_output=TopicInsightOutput)


# Simple summary chain — one-sentence TLDR for clusters with < 2 articles
SIMPLE_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior news analyst with CEO + AI/Technology analyst perspectives.\n"
            "Write a ONE-SENTENCE summary for this article cluster.\n"
            "Write in {target_lang}.",
        ),
        ("human", "Article:\n{article_titles}"),
    ]
)


def get_simple_summary_chain() -> Runnable:
    """Returns LCEL chain for simple one-sentence summaries."""
    return SIMPLE_SUMMARY_PROMPT | LLMWrapper() | StrOutputParser()
