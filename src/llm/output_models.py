"""Pydantic output models for LLM chain structured responses."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class ClassifyTranslateItem(BaseModel):
    """Single news classification and translation result."""

    id: Annotated[int, Field(ge=1, description="News ID (1-indexed integer)")]
    tags: list[str] = Field(
        description="List of 0-3 tags from candidate tag list, most specific first"
    )
    translation: str = Field(description="Translated news title in target language")


class ClassifyTranslateOutput(BaseModel):
    """Batch classification and translation output."""

    items: list[ClassifyTranslateItem] = Field(
        description="List of classification results, one per news item"
    )


# ---------------------------------------------------------------------------
# InsightChain models — replaces TLDRItem/Topic structure
# ---------------------------------------------------------------------------


class Insight(BaseModel):
    """Single insight within a topic."""

    title: str = Field(..., description="Insight subtitle")
    content: str = Field(..., description="2-4 sentence coherent paragraph")
    source_indices: list[int] = Field(
        ..., description="1-based article indices from the presented list"
    )


class Topic(BaseModel):
    """A topic within a cluster."""

    title: str = Field(..., description="Topic title in target language")
    summary: str = Field(..., description="One-sentence deep insight")
    insights: list[Insight] = Field(..., description="Multiple insights for this topic")


class TopicInsightOutput(BaseModel):
    """Output from InsightChain — variable-length list of topics."""

    topics: list[Topic] = Field(..., description="Topics worth deep-diving")
