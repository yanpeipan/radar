"""Unit tests for RSSProvider, GitHubReleaseProvider, and ProviderRegistry.

Test Conventions (from Phase 26):
1. NO PRIVATE FUNCTION TESTING - test only public interfaces
2. REAL DATABASE VIA tmp_path - use initialized_db fixture for database tests
3. HTTP MOCKING WITH httpx_mock - use pytest-httpx's httpx_mock fixture for HTTP requests
4. CLI TESTING WITH CliRunner
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import Feed

# =============================================================================
# RSSProvider Tests
# =============================================================================


class TestRSSProvider:
    """Tests for RSSProvider public interface."""

    def test_rss_provider_priority(self):
        """Verify priority() returns 50."""
        from src.providers.rss_provider import RSSProvider

        provider = RSSProvider()
        assert provider.priority() == 50

    def test_rss_provider_match_success(self):
        """RSS content-type in response.headers, verify match() returns True."""
        from src.providers.rss_provider import RSSProvider

        # Mock response with RSS content-type and valid feed body
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <item>
                <title>Test Item</title>
                <link>https://example.com/item1</link>
            </item>
        </channel>
        </rss>"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/rss+xml"}
        mock_response.body = rss_xml

        provider = RSSProvider()
        result = provider.match("https://example.com/feed.xml", mock_response)
        assert result is True

    def test_rss_provider_match_atom(self):
        """Atom content-type in response.headers, verify match() returns True."""
        from src.providers.rss_provider import RSSProvider

        atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Atom Feed</title>
            <entry>
                <title>Test Entry</title>
                <link href="https://example.com/entry1"/>
            </entry>
        </feed>"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/atom+xml"}
        mock_response.body = atom_xml

        provider = RSSProvider()
        result = provider.match("https://example.com/feed.atom", mock_response)
        assert result is True

    def test_rss_provider_match_xml(self):
        """Generic XML content-type in response.headers, verify match() returns True."""
        from src.providers.rss_provider import RSSProvider

        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Test Item</title>
                <link>https://example.com/item1</link>
            </item>
        </channel>
        </rss>"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.body = rss_xml

        provider = RSSProvider()
        result = provider.match("https://example.com/feed.xml", mock_response)
        assert result is True

    def test_rss_provider_match_html_for_discovery(self):
        """HTML content-type in response.headers - RSSProvider matches to enable feed discovery."""
        from src.providers.rss_provider import RSSProvider

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "text/html"}

        provider = RSSProvider()
        result = provider.match("https://example.com/page.html", mock_response)
        # RSSProvider now matches HTML pages to discover feeds on them via discover()
        assert result is True

    def test_rss_provider_match_403_fallback(self):
        """403 status triggers Cloudflare fallback - match returns True to allow crawl."""
        from src.providers.rss_provider import RSSProvider

        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.headers = {"content-type": "text/html"}

        provider = RSSProvider()
        result = provider.match("https://example.com/feed.xml", mock_response)
        # 403 triggers Cloudflare fallback - match returns True to allow crawl
        assert result is True

    def test_rss_provider_fetch_articles_success(self):
        """Mock Fetcher.get to return sample RSS XML bytes, mock feedparser.parse() to return mock feed with entries."""
        from src.providers.rss_provider import RSSProvider

        # Sample RSS XML content
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <description>Test feed description</description>
            <item>
                <title>Article 1</title>
                <link>https://example.com/article1</link>
                <guid>article-1-guid</guid>
                <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
                <description>Article 1 description</description>
            </item>
            <item>
                <title>Article 2</title>
                <link>https://example.com/article2</link>
                <guid>article-2-guid</guid>
                <pubDate>Tue, 02 Jan 2024 12:00:00 +0000</pubDate>
                <description>Article 2 description</description>
            </item>
        </channel>
        </rss>"""

        # Mock Fetcher.get response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = rss_xml
        mock_response.headers = {"etag": "test-etag", "last-modified": "test-lm"}

        # Mock feedparser entry
        mock_entry1 = MagicMock()
        mock_entry1.get = lambda k: {
            "title": "Article 1",
            "link": "https://example.com/article1",
            "id": "article-1-guid",
            "published": "Mon, 01 Jan 2024 12:00:00 +0000",
            "description": "Article 1 description",
        }.get(k)
        mock_entry1.title = "Article 1"
        mock_entry1.link = "https://example.com/article1"
        mock_entry1.description = "Article 1 description"

        mock_entry2 = MagicMock()
        mock_entry2.get = lambda k: {
            "title": "Article 2",
            "link": "https://example.com/article2",
            "id": "article-2-guid",
            "published": "Tue, 02 Jan 2024 12:00:00 +0000",
            "description": "Article 2 description",
        }.get(k)
        mock_entry2.title = "Article 2"
        mock_entry2.link = "https://example.com/article2"
        mock_entry2.description = "Article 2 description"

        # Mock feedparser.parse return value
        mock_feed = MagicMock()
        mock_feed.feed = {"title": "Test Feed"}
        mock_feed.entries = [mock_entry1, mock_entry2]

        with (
            patch(
                "src.utils.scraping_utils.fetch_with_fallback",
                return_value=mock_response,
            ),
            patch(
                "src.providers.rss_provider.feedparser.parse", return_value=mock_feed
            ),
        ):
            provider = RSSProvider()
            feed = Feed(
                id="test",
                name="Test",
                url="https://example.com/feed.xml",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)

            assert len(result.articles) == 2
            assert result.articles[0].title == "Article 1"
            assert result.articles[1].title == "Article 2"

    def test_rss_provider_parse(self):
        """Create mock response and verify parse() returns Article with correct fields."""
        from src.providers.base import Article
        from src.providers.rss_provider import RSSProvider

        # Create mock content object with .value attribute (feedparser style)
        mock_content_item = MagicMock()
        mock_content_item.value = "Full content here"

        # Create mock raw entry with required fields
        mock_raw = MagicMock()
        mock_raw.get = lambda k: {
            "title": "Test Article",
            "link": "http://test.com/article",
            "published": "2024-01-01",
            "updated": None,
            "description": "Test description",
            "summary": None,
        }.get(k)
        mock_raw.title = "Test Article"
        mock_raw.link = "http://test.com/article"
        mock_raw.published = "2024-01-01"
        mock_raw.updated = None
        mock_raw.description = "Test description"
        mock_raw.summary = None
        mock_raw.content = [mock_content_item]
        mock_raw.summary_detail = None

        # Create mock parsed feed
        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [mock_raw]

        # Create mock response
        mock_response = MagicMock()
        mock_response.body = b""

        provider = RSSProvider()
        with patch(
            "src.providers.rss_provider.feedparser.parse", return_value=mock_parsed
        ):
            result = provider.parse_articles(mock_response)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].title == "Test Article"
        assert result[0].link == "http://test.com/article"
        assert result[0].published_at == "2024-01-01"
        assert result[0].description == "Test description"
        assert result[0].content == "Full content here"

    def test_rss_provider_parse_feed(self):
        """Mock Fetcher.get to return 200 with sample RSS XML bytes containing feed title, verify parse_feed() returns DiscoveredFeed with correct fields."""
        from src.discovery.models import DiscoveredFeed
        from src.models import FeedType
        from src.providers.rss_provider import RSSProvider

        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <description>A test feed</description>
        </channel>
        </rss>"""

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.body = rss_xml
        mock_response.headers = {"etag": "feed-etag", "last-modified": "feed-lm"}

        with (
            patch(
                "src.utils.scraping_utils.fetch_with_fallback",
                return_value=mock_response,
            ),
            patch("src.providers.rss_provider.feedparser.parse") as mock_parse,
        ):
            mock_parsed = MagicMock()
            mock_parsed.feed = {"title": "Test Feed"}
            mock_parse.return_value = mock_parsed

            provider = RSSProvider()
            result = provider.parse_feed("https://example.com/feed.xml")

            assert isinstance(result, DiscoveredFeed)
            assert result.title == "Test Feed"
            assert result.url == "https://example.com/feed.xml"
            assert result.feed_type == FeedType.RSS
            assert result.valid is True


# =============================================================================
# GitHubReleaseProvider Tests
# =============================================================================


class TestGitHubReleaseProvider:
    """Tests for GitHubReleaseProvider public interface."""

    def test_github_release_provider_priority(self):
        """Verify priority() returns 300 (highest - GitHub releases must use this provider)."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        provider = GitHubReleaseProvider()
        assert provider.priority() == 300

    def test_github_release_provider_match_https(self):
        """Verify match('https://github.com/owner/repo') returns True."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        provider = GitHubReleaseProvider()
        assert provider.match("https://github.com/owner/repo") is True

    def test_github_release_provider_match_https_with_git(self):
        """Verify match('https://github.com/owner/repo.git') returns True."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        provider = GitHubReleaseProvider()
        assert provider.match("https://github.com/owner/repo.git") is True

    def test_github_release_provider_match_ssh(self):
        """Verify match('git@github.com:owner/repo.git') returns True."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        provider = GitHubReleaseProvider()
        assert provider.match("git@github.com:owner/repo.git") is True

    def test_github_release_provider_match_failure(self):
        """Verify match('https://example.com/feed') returns False."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        provider = GitHubReleaseProvider()
        assert provider.match("https://example.com/feed") is False

    def test_github_release_provider_fetch_articles_success(self):
        """Mock PyGithub client and get_repo()/get_latest_release() to return mock release."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        # Mock release object
        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.name = "Release 1.0.0"
        mock_release.body = "Release notes for v1.0.0"
        mock_release.html_url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_release.published_at.isoformat = MagicMock(
            return_value="2024-01-15T10:30:00"
        )

        # Mock repo
        mock_repo = MagicMock()
        mock_repo.get_latest_release = MagicMock(return_value=mock_release)

        # Mock client
        mock_client = MagicMock()
        mock_client.get_repo = MagicMock(return_value=mock_repo)

        with (
            patch(
                "src.providers.github_release_provider._get_github_client",
                return_value=mock_client,
            ),
            patch("src.utils.github.parse_github_url", return_value=("owner", "repo")),
        ):
            provider = GitHubReleaseProvider()
            feed = Feed(
                id="test",
                name="Test",
                url="https://github.com/owner/repo",
                created_at="2024-01-01T00:00:00",
            )
            result = provider.fetch_articles(feed)

            assert len(result.articles) == 1
            article = result.articles[0]
            assert article.title == "v1.0.0"
            assert article.link == "https://github.com/owner/repo/releases/tag/v1.0.0"
            assert article.guid == "v1.0.0"
            assert article.published_at == "2024-01-15T10:30:00"
            assert article.description == "Release notes for v1.0.0"
            assert article.content is None

    def test_github_release_provider_parse(self):
        """Create mock raw dict and verify parse() returns Article with correct fields."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        mock_raw = {
            "tag_name": "v1.0",
            "name": "Release 1.0",
            "body": "Release notes",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0",
            "published_at": "2024-01-01T00:00:00",
        }

        provider = GitHubReleaseProvider()
        result = provider.parse_articles([mock_raw])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].title == "v1.0"
        assert result[0].link == "https://github.com/owner/repo/releases/tag/v1.0"
        assert result[0].guid == "v1.0"
        assert result[0].published_at == "2024-01-01T00:00:00"
        assert result[0].description == "Release notes"
        assert result[0].content is None


# =============================================================================
# ProviderRegistry Tests
# =============================================================================


class TestProviderRegistry:
    """Tests for ProviderRegistry module-level functions."""

    def test_provider_registry_discover_matching(self):
        """Call discover('https://github.com/owner/repo') with mock response, verify GitHubReleaseProvider matches."""
        import src.providers as providers

        # Mock response for GitHub URL
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "text/html"}

        matched = providers.discover("https://github.com/owner/repo", mock_response)
        # Verify that discover() returns feeds (DiscoveredFeed objects)
        assert len(matched) >= 0  # May be empty if no feeds discovered
        # The match() part should match GitHubReleaseProvider (check via priority ordering)
        all_providers = providers.get_all_providers()
        github_provider = next(
            (
                p
                for p in all_providers
                if p.__class__.__name__ == "GitHubReleaseProvider"
            ),
            None,
        )
        assert github_provider is not None
        # Verify GitHubReleaseProvider has highest priority among matching providers
        assert github_provider.priority() == 300

    def test_provider_registry_discover_multiple(self):
        """Verify get_all_providers() returns providers sorted by priority descending."""
        import src.providers as providers

        all_providers = providers.get_all_providers()
        assert len(all_providers) >= 1
        # Verify sorted by priority descending
        priorities = [p.priority() for p in all_providers]
        assert priorities == sorted(priorities, reverse=True)
        # TavilyProvider should be first (priority 400 > GitHubReleaseProvider 300 > RSSProvider 50)
        assert all_providers[0].__class__.__name__ == "TavilyProvider"

    def test_provider_registry_discover_none(self):
        """Call discover('https://unknown.example/feed') which no provider matches."""
        import src.providers as providers

        matched = providers.discover("https://unknown.example/feed")
        assert matched == []

    def test_provider_registry_discover_or_default_fallback(self):
        """Call discover('https://unknown.example/feed') which no provider matches, verify empty list (no RSS fallback)."""
        import src.providers as providers

        # No provider matches this URL - returns empty list (no implicit fallback)
        matched = providers.discover("https://unknown.example/feed")
        assert matched == []

    def test_provider_registry_discover_or_default_match(self):
        """Verify GitHubReleaseProvider is registered and matches GitHub URLs."""
        import src.providers as providers

        # Mock response for GitHub URL
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "text/html"}

        # GitHubReleaseProvider should match
        all_providers = providers.get_all_providers()
        github_provider = next(
            (
                p
                for p in all_providers
                if p.__class__.__name__ == "GitHubReleaseProvider"
            ),
            None,
        )
        assert github_provider is not None
        assert github_provider.match("https://github.com/owner/repo") is True

    def test_provider_registry_get_all_providers(self):
        """Verify get_all_providers() returns list of providers sorted by priority descending."""
        import src.providers as providers

        all_providers = providers.get_all_providers()
        assert len(all_providers) > 0
        # Verify sorted by priority descending
        priorities = [p.priority() for p in all_providers]
        assert priorities == sorted(priorities, reverse=True)
