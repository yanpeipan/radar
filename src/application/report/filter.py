"""Layer 0: Signal Filter — rules-based article filtering."""

from __future__ import annotations

import hashlib
from typing import Any

# Event keywords that trigger a quality boost
_EVENT_KEYWORDS = [
    "release",
    "launch",
    "announce",
    "发布",
    "推出",
    "开源",
    "funding",
    "raise",
    "series",
    "vc",
    "融资",
    "投资",
    "acquisition",
    "merger",
    "收购",
    "合并",
    "regulation",
    "policy",
    "ban",
    "监管",
    "政策",
    "paper",
    "research",
    "study",
    "研究",
    "论文",
    "open source",
    "github",
    "pypi",
    "npm",
]


class SignalFilter:
    """Filter articles by quality signals to reduce from ~3333 to ~300."""

    def __init__(
        self,
        quality_threshold: float = 0.6,
        feed_weight_threshold: float = 0.5,
        event_signal_boost: bool = True,
    ):
        self.quality_threshold = quality_threshold
        self.feed_weight_threshold = feed_weight_threshold
        self.event_signal_boost = event_signal_boost

    def filter(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply all filter rules. Returns filtered articles."""
        seen_hashes: set[str] = set()
        result = []
        for article in articles:
            if self._passes_all_rules(article, seen_hashes):
                result.append(article)
        return result

    def _passes_all_rules(self, article: dict, seen_hashes: set[str]) -> bool:
        # Rule 1: SHA256 exact dedup (title + content[:500])
        content = article.get("content", "") or article.get("description", "") or ""
        content_preview = content[:500]
        h = hashlib.sha256(
            f"{article.get('title', '')}{content_preview}".encode()
        ).hexdigest()
        if h in seen_hashes:
            return False
        seen_hashes.add(h)

        # Rule 2: Quality gate (with optional event boost)
        quality = article.get("quality_score", 0.0)
        title = article.get("title", "")
        effective_quality = quality
        if self.event_signal_boost and self._has_event_signal(title):
            effective_quality += 0.1

        if effective_quality < self.quality_threshold:
            return False

        # Rule 3: Feed weight gate
        feed_weight = article.get("feed_weight", 0.0)
        return feed_weight >= self.feed_weight_threshold

    def _has_event_signal(self, title: str) -> bool:
        title_lower = title.lower()
        return any(kw in title_lower for kw in _EVENT_KEYWORDS)
