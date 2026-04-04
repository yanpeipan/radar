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
        assert (
            provider.match(
                "https://github.com/trending?since=daily&spoken_language_code=Python"
            )
            is True
        )

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
        result = provider.discover(
            "https://github.com/trending", mock_response, depth=1
        )
        assert result == []

    def test_fetch_articles_single_feed_fetches_three_periods(self):
        """Verify fetch_articles fetches daily, weekly, and monthly periods."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        # Track which URLs are fetched
        fetched_urls = []

        # Mock fetch_selector to track URLs and return empty results
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.css.return_value.all.return_value = []

        def mock_fetch_selector(url):
            fetched_urls.append(url)
            return mock_fetcher_instance

        with patch(
            "src.providers.github_trending_provider.fetch_selector"
        ) as mock_fetch:
            mock_fetch.side_effect = mock_fetch_selector

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

        # Mock entry with new scrapling 0.4.x API
        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.text = "/owner/repo"
        # For .css("::attr(href)").get().strip()
        mock_h2_a.css.return_value.get.return_value.strip.return_value = "/owner/repo"

        def make_selector_mock(text):
            mock_el = MagicMock()
            mock_el.text = text
            mock_el.css.return_value.get.return_value.strip.return_value = text
            return mock_el

        mock_p = make_selector_mock("Description")
        mock_lang = make_selector_mock("Python")
        mock_stars = make_selector_mock("1,500 stars today")
        mock_forks = make_selector_mock("200 forks")

        def entry_css(selector):
            mock_result = MagicMock()
            if selector == "h2 a":
                mock_result.first = mock_h2_a
            elif selector == "p":
                mock_result.first = mock_p
            elif selector == "span[itemprop='programmingLanguage']":
                mock_result.first = mock_lang
            elif selector == "a.Link--muted:nth-of-type(1)":
                mock_result.first = mock_stars
            elif selector == "a.Link--muted:nth-of-type(2)":
                mock_result.first = mock_forks
            else:
                mock_result.first = None
            return mock_result

        mock_entry.css = entry_css

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "weekly", 1)

        assert result is not None
        assert result.guid == "github-trending:weekly:https://github.com/owner/repo"

    def test_title_format(self):
        """Verify title format is '[stars★] user/repo: description'."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.text = "/owner/repo"
        mock_h2_a.css.return_value.get.return_value.strip.return_value = "/owner/repo"

        def make_selector_mock(text):
            mock_el = MagicMock()
            mock_el.text = text
            mock_el.css.return_value.get.return_value.strip.return_value = text
            return mock_el

        mock_p = make_selector_mock("A great library")
        mock_lang = make_selector_mock("Python")
        mock_stars = make_selector_mock("15,000 stars today")
        mock_forks = make_selector_mock("1,200 forks")

        def entry_css(selector):
            mock_result = MagicMock()
            if selector == "h2 a":
                mock_result.first = mock_h2_a
            elif selector == "p":
                mock_result.first = mock_p
            elif selector == "span[itemprop='programmingLanguage']":
                mock_result.first = mock_lang
            elif selector == "a.Link--muted:nth-of-type(1)":
                mock_result.first = mock_stars
            elif selector == "a.Link--muted:nth-of-type(2)":
                mock_result.first = mock_forks
            else:
                mock_result.first = None
            return mock_result

        mock_entry.css = entry_css

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "daily", 1)

        assert result is not None
        assert result.title == "[15000★] owner/repo: A great library"

    def test_metadata_json(self):
        """Verify metadata JSON contains stars, forks, language, rank, period."""
        import json

        from src.providers.github_trending_provider import GitHubTrendingProvider

        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.text = "/owner/repo"
        mock_h2_a.css.return_value.get.return_value.strip.return_value = "/owner/repo"

        def make_selector_mock(text):
            mock_el = MagicMock()
            mock_el.text = text
            mock_el.css.return_value.get.return_value.strip.return_value = text
            return mock_el

        mock_p = make_selector_mock("Description")
        mock_lang = make_selector_mock("Rust")
        mock_stars = make_selector_mock("8,000 stars today")
        mock_forks = make_selector_mock("400 forks")

        def entry_css(selector):
            mock_result = MagicMock()
            if selector == "h2 a":
                mock_result.first = mock_h2_a
            elif selector == "p":
                mock_result.first = mock_p
            elif selector == "span[itemprop='programmingLanguage']":
                mock_result.first = mock_lang
            elif selector == "a.Link--muted:nth-of-type(1)":
                mock_result.first = mock_stars
            elif selector == "a.Link--muted:nth-of-type(2)":
                mock_result.first = mock_forks
            else:
                mock_result.first = None
            return mock_result

        mock_entry.css = entry_css

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "monthly", 5)

        assert result is not None
        # meta field contains stars, forks, language, rank, period
        assert result.meta["stars"] == 8000
        assert result.meta["forks"] == 400
        assert result.meta["language"] == "Rust"
        assert result.meta["rank"] == 5
        assert result.meta["period"] == "monthly"

    def test_tags_format(self):
        """Verify tags format is 'language:X,stars:Y'."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        mock_entry = MagicMock()
        mock_h2_a = MagicMock()
        mock_h2_a.text = "/test/repo"
        mock_h2_a.css.return_value.get.return_value.strip.return_value = "/test/repo"

        def make_selector_mock(text):
            mock_el = MagicMock()
            mock_el.text = text
            mock_el.css.return_value.get.return_value.strip.return_value = text
            return mock_el

        mock_p = make_selector_mock("Desc")
        mock_lang = make_selector_mock("JavaScript")
        mock_stars = make_selector_mock("500 stars today")
        mock_forks = make_selector_mock("50 forks")

        def entry_css(selector):
            mock_result = MagicMock()
            if selector == "h2 a":
                mock_result.first = mock_h2_a
            elif selector == "p":
                mock_result.first = mock_p
            elif selector == "span[itemprop='programmingLanguage']":
                mock_result.first = mock_lang
            elif selector == "a.Link--muted:nth-of-type(1)":
                mock_result.first = mock_stars
            elif selector == "a.Link--muted:nth-of-type(2)":
                mock_result.first = mock_forks
            else:
                mock_result.first = None
            return mock_result

        mock_entry.css = entry_css

        provider = GitHubTrendingProvider()
        result = provider._parse_repo_entry(mock_entry, "daily", 1)

        assert result is not None
        assert result.tags == "language:JavaScript,stars:500"

    def test_rate_limit_handling(self):
        """Verify fetch returns empty articles on rate limit (429)."""
        from src.providers.github_trending_provider import GitHubTrendingProvider

        # Mock fetch_selector to raise exception (simulating rate limit)
        with patch(
            "src.providers.github_trending_provider.fetch_selector"
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("429 Too Many Requests")

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

        # Mock fetch_selector with no repo entries
        mock_fetcher_instance = MagicMock()
        mock_fetcher_instance.css.return_value.all.return_value = []

        with patch(
            "src.providers.github_trending_provider.fetch_selector"
        ) as mock_fetch:
            mock_fetch.return_value = mock_fetcher_instance

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
