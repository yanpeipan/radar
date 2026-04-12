"""LangChain LCEL chains for report generation."""

from __future__ import annotations

from typing import Annotated

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field

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
            'Return JSON object with "items" array, each element: {{"entity_id": "...", "tldr": "..."}}.',
        ),
    ]
)


def get_tldr_chain() -> Runnable:
    """Returns LCEL chain for batch TLDR generation using structured output.

    Uses .with_structured_output() for automatic Pydantic parsing instead of
    regex-based output parsing.
    """
    llm = _get_llm_wrapper(800)
    structured_llm = llm.with_structured_output(TLDRItems)
    return TLDR_PROMPT | structured_llm


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
    """Returns LCEL chain for batch news classification and translation.

    Uses .with_structured_output() for automatic Pydantic parsing.

    Args:
        tag_list: Newline-separated candidate tags
        news_list: Newline-separated news titles (one per line)
        target_lang: Target language code (default: zh)
    """
    llm = _get_llm_wrapper(16384)
    structured_llm = llm.with_structured_output(ClassifyTranslateOutput)
    return CLASSIFY_TRANSLATE_PROMPT | structured_llm


# ---------------------------------------------------------------------------
# LCEL Runnable factories for report pipeline (Phase 2 migration)
# ---------------------------------------------------------------------------


def make_classify_runnable(
    tag_list: str,
    target_lang: str = "zh",
    batch_size: int = 50,
    max_concurrency: int = 5,
) -> Runnable:
    """Factory for BatchClassifyChain as LCEL Runnable.

    DEPRECATED: Use this factory instead of BatchClassifyChain class directly.
    """
    from src.application.report.classify import BatchClassifyChain

    return BatchClassifyChain(
        tag_list=tag_list,
        target_lang=target_lang,
        batch_size=batch_size,
        max_concurrency=max_concurrency,
    )


def make_tldr_runnable(
    top_n: int = 100,
    target_lang: str = "zh",
    max_concurrency: int = 5,
) -> Runnable:
    """Factory for TLDRChain as LCEL Runnable.

    DEPRECATED: Use this factory instead of TLDRChain class directly.
    """
    from src.application.report.tldr import TLDRChain

    return TLDRChain(
        top_n=top_n,
        target_lang=target_lang,
        max_concurrency=max_concurrency,
    )


def make_build_report_runnable(
    heading_tree=None,
    target_lang: str = "zh",
) -> Runnable:
    """Factory for BuildReportDataChain as LCEL Runnable.

    DEPRECATED: Use this factory instead of BuildReportDataChain class directly.
    """
    from src.application.report.models import BuildReportDataChain

    return BuildReportDataChain(
        heading_tree=heading_tree,
        target_lang=target_lang,
    )
