"""Unit tests for GitHubTrendingProvider.

Test coverage:
- URL matching (github.com/trending with/without since param)
- Priority verification
- Article fetching with mocked HTML
- GUID format verification
- Title format verification
- Metadata JSON structure
- Feed parsing
- Rate limit handling
"""

from unittest.mock import MagicMock, patch

import pytest

from src.models import Feed


class TestGitHubTrendingProvider:
    """Tests for GitHubTrendingProvider public interface."""

    def test_match_github_trending_url(self):
        """Verify match('https://github.com/trending') returns True."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://github.com/trending") is True

    def test_match_github_trending_url_http(self):
        """Verify match('http://github.com/trending') returns True."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("http://github.com/trending") is True

    def test_match_with_since_param_daily(self):
        """Verify match('github.com/trending?since=daily') returns True."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://github.com/trending?since=daily") is True

    def test_match_with_since_param_weekly(self):
        """Verify match('github.com/trending?since=weekly') returns True."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://github.com/trending?since=weekly") is True

    def test_match_with_since_param_monthly(self):
        """Verify match('github.com/trending?since=monthly') returns True."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://github.com/trending?since=monthly") is True

    def test_match_with_language_param(self):
        """Verify match('github.com/trending?since=daily&spoken_language_code=Python') returns True."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://github.com/trending?since=daily&spoken_language_code=Python") is True

    def test_match_non_trending(self):
        """Verify match('https://github.com/owner/repo') returns False."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://github.com/owner/repo") is False

    def test_match_non_github(self):
        """Verify match('https://example.com/trending') returns False."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.match("https://example.com/trending") is False

    def test_priority(self):
        """Verify priority() returns 300 (same as GitHubReleaseProvider)."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        assert provider.priority() == 300

    def test_parse_feed(self):
        """Verify parse_feed returns DiscoveredFeed with correct fields."""
        from src.discovery.models import DiscoveredFeed
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        result = provider.parse_feed("https://github.com/trending")

        assert isinstance(result, DiscoveredFeed)
        assert result.title == "GitHub Trending"
        assert result.url == "https://github.com/trending"
        assert result.feed_type == "github_trending"
        assert result.valid is True

    def test_parse_feed_invalid(self):
        """Verify parse_feed returns invalid DiscoveredFeed for non-trending URL."""
        from src.discovery.models import DiscoveredFeed
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        result = provider.parse_feed("https://github.com/owner/repo")

        assert isinstance(result, DiscoveredFeed)
        assert result.valid is False

    def test_discover(self):
        """Verify discover returns empty list (no discovery for trending URLs)."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        result = provider.discover("https://github.com/trending")
        assert result == []

    def test_discover_with_response(self):
        """Verify discover returns empty list even with response (no discovery)."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        provider = GitHubTrendingProvider()
        mock_response = MagicMock()
        result = provider.discover("https://github.com/trending", mock_response, depth=1)
        assert result == []

    def test_fetch_articles_single_feed_fetches_three_periods(self):
        """Verify fetch_articles fetches daily, weekly, and monthly periods."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        # Mock Fetcher.fetch to return empty results (just tracking URLs)
        mock_fetcher = MagicMock()
        mock_fetcher.css.return_value.all.return_value = []

        # Track which URLs are fetched
        fetched_urls = []

        def mock_fetch(url):
            fetched_urls.append(url)
            return mock_fetcher

        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.css.return_value.all.return_value = []

        with patch("src.providers.github_trending_provider.Fetcher") as mock_fetcher_class:
            mock_fetcher_class.fetch = mock_fetch

            provider = GitHubTrendingProvider()
            feed = Feed(
                id="test",
                name="GitHub Trending",
                url="https://github.com/trending",
                created_at="2024-01-01T00:00:00",
            )
            provider.fetch_articles(feed)

            # Should have fetched all 3 periods
            assert len(fetched_urls) == 3
            assert "https://github.com/trending?since=daily" in fetched_urls
            assert "https://github.com/trending?since=weekly" in fetched_urls
            assert "https://github.com/trending?since=monthly" in fetched_urls

    def test_guid_format(self):
        """Verify GUID format is 'github-trending:{period}:{repo_url}'."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        # Mock Fetcher response
        mock_entry = MagicMock()
        mock_entry.css_first.side_effect = lambda selector: {
            "h2 a": MagicMock(css_first=MagicMock(return_value="/owner/repo"), text="/owner/repo"),
            "p": MagicMock(text="Description"),
            "span[itemprop='programmingLanguage']": MagicMock(text="Python"),
            "a.Link--muted:nth-of-type(2)": MagicMock(text="1,500 stars today"),
            "a.Link--muted:nth-of-type(3)": MagicMock(text="200 forks"),
        }.get(selector, MagicMock(return_value=None))()

        # Create mock article by calling _parse_repo_entry
        provider = GitHubTrendingProvider()

        # We need to mock the entry's methods properly
        mock_h2_a = MagicMock()
        mock_h2_a.css_first = MagicMock(return_value="/owner/repo")
        mock_h2_a.text = "/owner/repo"

        mock_entry.css_first = MagicMock(side_effect=lambda sel: {
            "h2 a": mock_h2_a,
            "p": MagicMock(text="Description"),
            "span[itemprop='programmingLanguage']": MagicMock(text="Python"),
            "a.Link--muted:nth-of-type(2)": MagicMock(text="1,500 stars today"),
            "a.Link--muted:nth-of-type(3)": MagicMock(text="200 forks"),
        }.get(sel))

        result = provider._parse_repo_entry(mock_entry, "weekly", 1)

        assert result is not None
        assert result["guid"] == "github-trending:weekly:https://github.com/owner/repo"

    def test_title_format(self):
        """Verify title format is '[stars★] user/repo: description'."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.css_first = MagicMock(return_value="/owner/repo")
        mock_h2_a.text = "/owner/repo"

        mock_entry.css_first = MagicMock(side_effect=lambda sel: {
            "h2 a": mock_h2_a,
            "p": MagicMock(text="A great library"),
            "span[itemprop='programmingLanguage']": MagicMock(text="Python"),
            "a.Link--muted:nth-of-type(2)": MagicMock(text="15,000 stars today"),
            "a.Link--muted:nth-of-type(3)": MagicMock(text="1,200 forks"),
        }.get(sel))

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "daily", 1)

        assert result is not None
        assert result["title"] == "[15000★] owner/repo: A great library"

    def test_metadata_json(self):
        """Verify metadata JSON contains stars, forks, language, rank, period."""
        import json

        from src.providers.github_trending_provider import GitHubTrendingProvider

        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.css_first = MagicMock(return_value="/owner/repo")
        mock_h2_a.text = "/owner/repo"

        mock_entry.css_first = MagicMock(side_effect=lambda sel: {
            "h2 a": mock_h2_a,
            "p": MagicMock(text="Description"),
            "span[itemprop='programmingLanguage']": MagicMock(text="Rust"),
            "a.Link--muted:nth-of-type(2)": MagicMock(text="8,000 stars today"),
            "a.Link--muted:nth-of-type(3)": MagicMock(text="400 forks"),
        }.get(sel))

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "monthly", 5)

        assert result is not None
        # content field should be JSON with metadata
        metadata = json.loads(result["content"])
        assert metadata["stars"] == 8000
        assert metadata["forks"] == 400
        assert metadata["language"] == "Rust"
        assert metadata["rank"] == 5
        assert metadata["period"] == "monthly"

    def test_tags_format(self):
        """Verify tags format is 'language:X,stars:Y'."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.css_first = MagicMock(return_value="/test/repo")
        mock_h2_a.text = "/test/repo"

        mock_entry.css_first = MagicMock(side_effect=lambda sel: {
            "h2 a": mock_h2_a,
            "p": MagicMock(text="Desc"),
            "span[itemprop='programmingLanguage']": MagicMock(text="JavaScript"),
            "a.Link--muted:nth-of-type(2)": MagicMock(text="500 stars today"),
            "a.Link--muted:nth-of-type(3)": MagicMock(text="50 forks"),
        }.get(sel))

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "daily", 1)

        assert result is not None
        assert result["tags"] == "language:JavaScript,stars:500"

    def test_rate_limit_handling(self):
        """Verify fetch returns empty articles on rate limit (429)."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        # Mock Fetcher.fetch to raise exception (simulating rate limit)
        with patch("src.providers.github_trending_provider.Fetcher") as mock_fetcher_class:
            mock_fetcher_class.fetch.side_effect = Exception("429 Too Many Requests")

            provider = GitHubTrendingProvider()
            feed = Feed(
                id="test",
                name="GitHub Trending",
                url="https://github.com/trending",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)

            # Should return empty articles due to rate limit
            assert result.articles == []

    def test_fetch_articles_empty_response(self):
        """Verify fetch returns empty articles when no repos found."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        # Mock Fetcher with no repo entries
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.css.return_value.all.return_value = []

        with patch("src.providers.github_trending_provider.Fetcher") as mock_fetcher_class:
            mock_fetcher_class.fetch.return_value = mock_fetcher_instance

            provider = GitHubTrendingProvider()
            feed = Feed(
                id="test",
                name="GitHub Trending",
                url="https://github.com/trending",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)

            # Should return empty articles
            assert result.articles == []
