"""Layer 0: Signal filter - exact dedup + quality gate + feed_weight gate."""

import hashlib
from typing import Any


class SignalFilter:
    """Filter articles by exact dedup, quality score, and feed weight thresholds.

    Rules applied in order:
    1. Exact dedup via SHA256(title + content[:500])
    2. quality_score >= quality_threshold (default 0.6)
    3. feed_weight >= feed_weight_threshold (default 0.5)
    """

    def __init__(
        self,
        quality_threshold: float = 0.6,
        feed_weight_threshold: float = 0.5,
    ) -> None:
        self.quality_threshold = quality_threshold
        self.feed_weight_threshold = feed_weight_threshold
        self._seen_hashes: set[str] = set()

    def _content_hash(self, title: str, content: str) -> str:
        """Compute SHA256 hash of title + first 500 chars of content."""
        text = f"{title}{content[:500]}"
        return hashlib.sha256(text.encode()).hexdigest()

    def filter(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply dedup + quality + feed_weight gates, return filtered list."""
        filtered = []
        for article in articles:
            title = article.get("title", "")
            content = article.get("content") or article.get("description") or ""
            h = self._content_hash(title, content)
            if h in self._seen_hashes:
                continue
            quality = article.get("quality_score") or 0.0
            feed_weight = article.get("feed_weight") or 0.0
            if quality < self.quality_threshold:
                continue
            if feed_weight < self.feed_weight_threshold:
                continue
            self._seen_hashes.add(h)
            filtered.append(article)
        return filtered
