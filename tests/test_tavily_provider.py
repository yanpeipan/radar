"""Unit tests for TavilyProvider.

Test coverage:
- URL matching (search:, tavily:)
- Priority verification
- Article fetching with mocked SDK
- API key handling
- Feed parsing
- Discovery (returns empty)
"""

from unittest.mock import MagicMock, patch

import pytest

from src.models import Feed


class TestTavilyProvider:
    """Tests for TavilyProvider public interface."""

    def test_match_search_url(self):
        """Verify match('search:AI') returns True."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.match("search:AI") is True

    def test_match_search_url_with_spaces(self):
        """Verify match('search: machine learning') returns True."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.match("search: machine learning") is True

    def test_match_tavily_url(self):
        """Verify match('tavily:news') returns True."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.match("tavily:news") is True

    def test_match_tavily_url_complex(self):
        """Verify match('tavily:Python tutorials 2024') returns True."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.match("tavily:Python tutorials 2024") is True

    def test_match_non_tavily_url(self):
        """Verify match('https://example.com/feed') returns False."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.match("https://example.com/feed") is False

    def test_match_github_url(self):
        """Verify match('https://github.com/trending') returns False."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.match("https://github.com/trending") is False

    def test_priority(self):
        """Verify priority() returns 400 (highest)."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        assert provider.priority() == 400

    def test_fetch_articles_success(self):
        """Mock Tavily SDK response, verify articles are correctly mapped."""
        from src.providers.tavily_provider import TavilyProvider

        # Mock Tavily API response
        mock_response = {
            "results": [
                {
                    "title": "Article 1",
                    "url": "https://example.com/article1",
                    "description": "Description 1",
                    "content": "Full content 1",
                    "categories": ["tech", "AI"],
                },
                {
                    "title": "Article 2",
                    "url": "https://example.com/article2",
                    "description": "Description 2",
                    "content": None,
                    "categories": [],
                },
            ]
        }

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default=None: {
            "tavily.api_key": "test-api-key",
            "tavily.default_search_depth": "advanced",
            "tavily.default_max_results": 10,
        }.get(key, default)

        with (
            patch(
                "src.providers.tavily_provider._get_settings",
                return_value=mock_settings,
            ),
            patch("tavily.TavilyClient") as mock_tavily_class,
        ):
            # Setup mock client
            mock_client = MagicMock()
            mock_client.search.return_value = mock_response
            mock_tavily_class.return_value = mock_client

            provider = TavilyProvider()
            feed = Feed(
                id="test",
                name="Test Search",
                url="search:AI",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)

            assert len(result.articles) == 2

            # Verify first article mapping
            article1 = result.articles[0]
            assert article1["title"] == "Article 1"
            assert article1["link"] == "https://example.com/article1"
            assert article1["guid"] == "https://example.com/article1"
            assert article1["description"] == "Description 1"
            assert article1["content"] == "Full content 1"
            assert article1["tags"] == "tech,AI"

            # Verify second article (no content, no categories)
            article2 = result.articles[1]
            assert article2["title"] == "Article 2"
            assert article2["content"] is None
            assert article2["tags"] == ""

    def test_fetch_articles_no_keyword(self):
        """Verify fetch returns empty when URL has no keyword."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        feed = Feed(
            id="test",
            name="Test",
            url="search:",
            created_at="2024-01-01T00:00:00",
        )
        result = provider.fetch_articles(feed)
        assert result.articles == []

    def test_fetch_articles_no_api_key(self):
        """Verify fetch returns empty when API key is not configured."""
        from src.providers.tavily_provider import TavilyProvider

        # Mock settings with no API key
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default=None: {
            "tavily.api_key": None,
        }.get(key, default)

        with patch(
            "src.providers.tavily_provider._get_settings", return_value=mock_settings
        ):
            provider = TavilyProvider()
            feed = Feed(
                id="test",
                name="Test",
                url="search:AI",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)
            assert result.articles == []

    def test_fetch_articles_sdk_error(self):
        """Verify fetch returns empty on SDK error."""
        from src.providers.tavily_provider import TavilyProvider

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.get.side_effect = lambda key, default=None: {
            "tavily.api_key": "test-key",
            "tavily.default_search_depth": "advanced",
            "tavily.default_max_results": 10,
        }.get(key, default)

        with (
            patch(
                "src.providers.tavily_provider._get_settings",
                return_value=mock_settings,
            ),
            patch("tavily.TavilyClient") as mock_tavily_class,
        ):
            # Setup mock client to raise exception
            mock_client = MagicMock()
            mock_client.search.side_effect = Exception("API Error")
            mock_tavily_class.return_value = mock_client

            provider = TavilyProvider()
            feed = Feed(
                id="test",
                name="Test",
                url="search:AI",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)
            assert result.articles == []

    def test_parse_feed(self):
        """Verify parse_feed returns DiscoveredFeed with correct fields."""
        from src.discovery.models import DiscoveredFeed
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        result = provider.parse_feed("search:AI")

        assert isinstance(result, DiscoveredFeed)
        assert result.title == "Search: AI"
        assert result.url == "search:AI"
        assert result.feed_type == "tavily"
        assert result.valid is True

    def test_parse_feed_no_keyword(self):
        """Verify parse_feed returns invalid DiscoveredFeed when keyword is empty."""
        from src.discovery.models import DiscoveredFeed
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        result = provider.parse_feed("search:")

        assert isinstance(result, DiscoveredFeed)
        assert result.valid is False

    def test_discover(self):
        """Verify discover returns empty list (no discovery for search URLs)."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        result = provider.discover("search:AI")
        assert result == []

    def test_discover_with_response(self):
        """Verify discover returns empty list even with response (no discovery)."""
        from src.providers.tavily_provider import TavilyProvider

        provider = TavilyProvider()
        mock_response = MagicMock()
        result = provider.discover("search:AI", mock_response, depth=1)
        assert result == []
