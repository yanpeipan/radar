"""LangChain LCEL chains for report generation."""

from __future__ import annotations

import json

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from src.llm.core import LLMWrapper
from src.llm.output_models import (
    ClassifyTranslateOutput,
    ClusterInsightOutput,
    TopicInsightOutputDeprecated,
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
    return CLASSIFY_TRANSLATE_PROMPT | LLMWrapper(
        structured_output=ClassifyTranslateOutput
    )


# ---------------------------------------------------------------------------
# InsightChain chains — generate cluster.summary and cluster.children (Topics)
# ---------------------------------------------------------------------------

# Insight chain — generate topics with insights for rich clusters (>= 2 articles)
INSIGHT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a Principal Tech Strategist & Open-Source Trend Forecaster.\n"
            "Each cluster contains multiple related articles on the same subject.\n"
            "Apply a 4-step analytical framework to each topic:\n"
            "1. Surface Deconstruction: categorize and decompose surface-level elements\n"
            "2. First Principles Breakdown: identify the ROOT CAUSE driving this development\n"
            "3. Hidden Storylines: uncover shadow trends, unspoken consensus among elite developers\n"
            "4. Value Creator Translation: translate technical shifts into actionable alpha\n\n"
            "OUTPUT REQUIREMENTS:\n"
            "- summary: standalone one-sentence TLDR (independent洞察)\n"
            "- insight.title: categorizes the type (e.g. '监管转向', '平台战略', '技术范式转移')\n"
            "- insight.content: 2-4 sentence coherent paragraph that weaves together ROOT CAUSE + HIDDEN DYNAMICS + ACTIONABLE ALPHA\n"
            "Go beyond 'what happened' — aggressively mine for 'why' and 'so what'.",
        ),
        (
            "human",
            "Write in {target_lang}.\n\n"
            "Cluster articles (top {top_n}):\n{article_titles}",
        ),
    ]
)


def get_insight_chain() -> Runnable:
    """DEPRECATED: Returns LCEL chain for batch topic insight generation."""
    return INSIGHT_PROMPT | LLMWrapper(structured_output=TopicInsightOutputDeprecated)


# ClusterInsight chain — flat output with title/summary/content + embedded topics
CLUSTER_INSIGHT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a Principal Tech Strategist & Open-Source Trend Forecaster.\n"
            "Each cluster contains multiple related articles on the same subject.\n"
            "Apply a 4-step analytical framework to each topic:\n"
            "1. Surface Deconstruction: categorize and decompose surface-level elements\n"
            "2. First Principles Breakdown: identify the ROOT CAUSE driving this development\n"
            "3. Hidden Storylines: uncover shadow trends, unspoken consensus among elite developers\n"
            "4. Value Creator Translation: translate technical shifts into actionable alpha\n\n"
            "OUTPUT REQUIREMENTS:\n"
            "- title: cluster title in target language (e.g. '监管转向', '平台战略')\n"
            "- summary: standalone one-sentence TLDR (independent洞察)\n"
            "- content: 2-4 sentence coherent paragraph that weaves ROOT CAUSE + HIDDEN DYNAMICS + ACTIONABLE ALPHA\n"
            "- topics[].title: sub-topic categorization (e.g. '技术范式转移', '生态整合')\n"
            "- topics[].summary: one-sentence deep insight for the sub-topic\n"
            "- topics[].content: 2-4 sentence coherent paragraph for the sub-topic\n"
            "- topics[].source_indices: 1-based article indices from the presented list that support this topic\n"
            "Go beyond 'what happened' — aggressively mine for 'why' and 'so what'.",
        ),
        (
            "human",
            "Write in {target_lang}.\n\n"
            "Cluster articles (top {top_n}):\n{article_titles}",
        ),
    ]
)


def get_cluster_insight_chain() -> Runnable:
    """Returns LCEL chain for ClusterProcessChain with flat ClusterInsightOutput."""
    return CLUSTER_INSIGHT_PROMPT | LLMWrapper(structured_output=ClusterInsightOutput)


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
