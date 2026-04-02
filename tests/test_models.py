"""Unit tests for Pydantic models.

Test Conventions:
1. NO PRIVATE FUNCTION TESTING - test only public interfaces
2. REAL DATABASE VIA tmp_path - use initialized_db fixture for database tests
3. Test Pydantic model validation for Feed model
"""

import pytest
from pydantic import ValidationError


class TestFeedModelGroup:
    """Tests for Feed model group field validation."""

    def test_feed_group_max_length_100(self):
        """Feed model rejects group strings exceeding 100 characters."""
        from src.models import Feed

        # 100 chars is valid
        valid_group = "A" * 100
        feed = Feed(
            id="test-feed-1",
            name="Test Feed",
            url="https://example.com/feed.xml",
            created_at="2024-01-01T00:00:00+00:00",
            group=valid_group,
        )
        assert feed.group == valid_group

        # 101 chars should fail
        invalid_group = "A" * 101
        with pytest.raises(ValidationError) as exc_info:
            Feed(
                id="test-feed-2",
                name="Test Feed",
                url="https://example.com/feed2.xml",
                created_at="2024-01-01T00:00:00+00:00",
                group=invalid_group,
            )
        assert "String should have at most 100 characters" in str(exc_info.value)

    def test_feed_group_accepts_valid_string(self):
        """Feed model accepts valid group names."""
        from src.models import Feed

        # Various valid group names
        valid_groups = [
            "LLM",
            "AI",
            "Machine Learning",
            "tech-news",
            "Newsletter #1",
            "日本語",
        ]

        for i, group in enumerate(valid_groups):
            feed = Feed(
                id=f"test-feed-{i}",
                name=f"Test Feed {i}",
                url=f"https://example.com/feed{i}.xml",
                created_at="2024-01-01T00:00:00+00:00",
                group=group,
            )
            assert feed.group == group

    def test_feed_group_default_none(self):
        """Feed model defaults group to None when not specified."""
        from src.models import Feed

        feed = Feed(
            id="test-feed-default",
            name="Test Feed",
            url="https://example.com/feed.xml",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert feed.group is None

    def test_feed_group_explicit_none(self):
        """Feed model accepts explicit None for group."""
        from src.models import Feed

        feed = Feed(
            id="test-feed-explicit-none",
            name="Test Feed",
            url="https://example.com/feed.xml",
            created_at="2024-01-01T00:00:00+00:00",
            group=None,
        )
        assert feed.group is None

    def test_feed_group_unicode_support(self):
        """Feed model supports unicode group names."""
        from src.models import Feed

        # Chinese characters
        feed_cn = Feed(
            id="test-feed-cn",
            name="Test Feed CN",
            url="https://example.com/cn.xml",
            created_at="2024-01-01T00:00:00+00:00",
            group="机器学习",
        )
        assert feed_cn.group == "机器学习"

        # Emoji
        feed_emoji = Feed(
            id="test-feed-emoji",
            name="Test Feed Emoji",
            url="https://example.com/emoji.xml",
            created_at="2024-01-01T00:00:00+00:00",
            group="📰 News",
        )
        assert feed_emoji.group == "📰 News"
