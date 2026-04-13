"""LangChain LCEL chains for report generation."""

from __future__ import annotations

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
            'Return JSON object with "items" array, each element: {{"id": int, "tags": [], "translation": "..."}}\n\n'
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
            "You are a senior news analyst with CEO + AI/Technology analyst dual perspectives.\n"
            "Each cluster has multiple related articles on the same subject.\n"
            "Generate TOPICS worth deep-diving (only if 2+ articles can be synthesized).\n"
            "Each topic: topic_id, title, summary (one sentence), multiple insights.\n"
            "Each insight: title, content (2-4 sentences), source_indices (1-based).\n"
            "Write in {target_lang}.\n"
            "Return JSON with 'topics' array.",
        ),
        (
            "human",
            "Cluster articles (top {top_n}):\n"
            "{article_titles}\n\n"
            "Return JSON with 'topics' array.",
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
