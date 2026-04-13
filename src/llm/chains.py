"""LangChain LCEL chains for report generation."""

from __future__ import annotations

from typing import Annotated

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

from src.llm.core import LLMWrapper
from src.llm.output_models import (
    ClassifyTranslateOutput,
    TLDRItem,
)

# ---------------------------------------------------------------------------
# Wrapper schemas for list outputs (required for .with_structured_output())
# ---------------------------------------------------------------------------


class TLDRItems(BaseModel):
    """Wrapper for list of TLDR items (required for structured output)."""

    items: Annotated[list[TLDRItem], Field(description="List of TLDR items")]


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
            'Return JSON object with "items" array, each element: {{"entity_id": "...", "tldr": "..."}}.',
        ),
    ]
)


def get_tldr_chain() -> Runnable:
    """Returns LCEL chain for batch TLDR generation."""
    return TLDR_PROMPT | LLMWrapper(structured_output=TLDRItems)


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
    return (
        CLASSIFY_TRANSLATE_PROMPT
        | LLMWrapper(structured_output=ClassifyTranslateOutput)
    )
