"""Unified score combination using Newton's cooling law for freshness.

This module provides combine_scores() which merges multiple scoring signals
into a final ranking score using weighted combination with time-decay freshness.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.articles import ArticleListItem

from src.storage.vector import _published_at_to_timestamp


def combine_scores(
    candidates: list[ArticleListItem],
    alpha: float = 0.3,
    beta: float = 0.3,
    gamma: float = 0.2,
    delta: float = 0.2,
) -> list[ArticleListItem]:
    """Combine multiple scoring signals into score using weighted combination.

    Newton's cooling law: freshness = exp(-days_ago / half_life_days)
    half_life_days is fixed at 7 (one week).

    Args:
        candidates: List of ArticleListItem candidates to score.
        alpha: Weight for Cross-Encoder score (ce_score).
        beta: Weight for freshness (time decay).
        gamma: Weight for vector similarity (vec_sim).
        delta: Weight for BM25 score (bm25_score).

    Returns:
        List of candidates sorted by score descending.
    """
    half_life_days = 7
    now = datetime.now(timezone.utc)

    for c in candidates:
        # Calculate freshness using Newton's cooling law
        if c.published_at:
            timestamp = _published_at_to_timestamp(c.published_at)
            if timestamp is not None:
                pub_dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                days_ago = (now - pub_dt).days
                c.freshness = math.exp(-days_ago / half_life_days)
            else:
                c.freshness = 0.0
        else:
            c.freshness = 0.0

        # ce_score = 0 means not reranked, treat as no contribution
        ce = c.ce_score if c.ce_score > 0 else 0.0

        # Final score = weighted combination of 4 signals
        c.score = (
            alpha * ce + beta * c.freshness + gamma * c.vec_sim + delta * c.bm25_score
        )

    candidates.sort(key=lambda x: x.score, reverse=True)
    return candidates
