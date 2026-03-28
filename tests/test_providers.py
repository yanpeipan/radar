"""Unit tests for RSSProvider, GitHubReleaseProvider, and ProviderRegistry.

Test Conventions (from Phase 26):
1. NO PRIVATE FUNCTION TESTING - test only public interfaces
2. REAL DATABASE VIA tmp_path - use initialized_db fixture for database tests
3. HTTP MOCKING WITH httpx_mock - use pytest-httpx's httpx_mock fixture for HTTP requests
4. CLI TESTING WITH CliRunner
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


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

    def test_rss_provider_match_success(self, httpx_mock):
        """Mock httpx.head() to return 200 with content-type application/rss+xml, verify match() returns True."""
        from src.providers.rss_provider import RSSProvider

        # Mock response with RSS content-type
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/rss+xml"}

        with patch("src.providers.rss_provider.httpx.head", return_value=mock_response):
            provider = RSSProvider()
            result = provider.match("https://example.com/feed.xml")
            assert result is True

    def test_rss_provider_match_atom(self, httpx_mock):
        """Mock httpx.head() to return 200 with content-type application/atom+xml, verify match() returns True."""
        from src.providers.rss_provider import RSSProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/atom+xml"}

        with patch("src.providers.rss_provider.httpx.head", return_value=mock_response):
            provider = RSSProvider()
            result = provider.match("https://example.com/feed.atom")
            assert result is True

    def test_rss_provider_match_xml(self, httpx_mock):
        """Mock httpx.head() to return 200 with content-type application/xml, verify match() returns True."""
        from src.providers.rss_provider import RSSProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml"}

        with patch("src.providers.rss_provider.httpx.head", return_value=mock_response):
            provider = RSSProvider()
            result = provider.match("https://example.com/feed.xml")
            assert result is True

    def test_rss_provider_match_failure(self, httpx_mock):
        """Mock httpx.head() to return 200 with content-type text/html, verify match() returns False."""
        from src.providers.rss_provider import RSSProvider

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}

        with patch("src.providers.rss_provider.httpx.head", return_value=mock_response):
            provider = RSSProvider()
            result = provider.match("https://example.com/page.html")
            assert result is False

    def test_rss_provider_match_403_fallback(self, httpx_mock):
        """Mock httpx.head() to return 403, verify match() returns True (Cloudflare fallback)."""
        from src.providers.rss_provider import RSSProvider
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"content-type": "text/html"}

        with patch("src.providers.rss_provider.httpx.head", return_value=mock_response):
            provider = RSSProvider()
            result = provider.match("https://example.com/feed.xml")
            # 403 triggers Cloudflare fallback - match returns True to allow crawl
            assert result is True

    def test_rss_provider_crawl_success(self, httpx_mock):
        """Mock httpx.get() to return sample RSS XML bytes, mock feedparser.parse() to return mock feed with entries."""
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

        # Mock httpx.get response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = rss_xml
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

        with patch("src.providers.rss_provider.httpx.get", return_value=mock_response):
            with patch("src.providers.rss_provider.feedparser.parse", return_value=mock_feed):
                provider = RSSProvider()
                result = provider.crawl("https://example.com/feed.xml")

                assert len(result) == 2
                assert result[0].get("title") == "Article 1"
                assert result[1].get("title") == "Article 2"

    @pytest.mark.asyncio
    async def test_rss_provider_crawl_async_success(self, httpx_mock):
        """Mock httpx.AsyncClient to return mock response with RSS XML bytes, verify crawl_async() returns list of entries."""
        from src.providers.rss_provider import RSSProvider

        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <item>
                <title>Async Article</title>
                <link>https://example.com/async-article</link>
                <guid>async-article-guid</guid>
                <pubDate>Wed, 03 Jan 2024 12:00:00 +0000</pubDate>
                <description>Async article description</description>
            </item>
        </channel>
        </rss>"""

        # Mock async client response - this is what fetch_feed_content_async receives
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = rss_xml
        mock_response.headers = {"etag": "async-etag"}
        mock_response.raise_for_status = MagicMock()

        # Mock the response returned by client.get() - must be awaitable
        async def mock_get(*args, **kwargs):
            return mock_response

        # Create async client instance that works as async context manager
        mock_async_client_instance = MagicMock()
        mock_async_client_instance.__aenter__ = AsyncMock(return_value=mock_async_client_instance)
        mock_async_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_async_client_instance.get = mock_get

        mock_async_client_class = MagicMock(return_value=mock_async_client_instance)

        # Mock feedparser entry
        mock_entry = MagicMock()
        mock_entry.get = lambda k: {
            "title": "Async Article",
            "link": "https://example.com/async-article",
            "id": "async-article-guid",
            "published": "Wed, 03 Jan 2024 12:00:00 +0000",
            "description": "Async article description",
        }.get(k)
        mock_entry.title = "Async Article"
        mock_entry.link = "https://example.com/async-article"
        mock_entry.description = "Async article description"

        mock_feed = MagicMock()
        mock_feed.feed = {"title": "Test Feed"}
        mock_feed.entries = [mock_entry]

        with patch("src.providers.rss_provider.httpx.AsyncClient", mock_async_client_class):
            with patch("src.providers.rss_provider.feedparser.parse", return_value=mock_feed):
                provider = RSSProvider()
                result = await provider.crawl_async("https://example.com/feed.xml")

                assert len(result.entries) == 1
                assert result.entries[0].get("title") == "Async Article"

    def test_rss_provider_parse(self):
        """Create mock raw entry and verify parse() returns Article with correct fields."""
        from src.providers.rss_provider import RSSProvider
        from src.providers.base import Article

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

        provider = RSSProvider()
        result = provider.parse(mock_raw)

        # Result is a dict (Article is dict in this codebase)
        assert isinstance(result, dict)
        assert result["title"] == "Test Article"
        assert result["link"] == "http://test.com/article"
        assert result["pub_date"] == "2024-01-01"
        assert result["description"] == "Test description"
        assert result["content"] == "Full content here"

    def test_rss_provider_feed_meta(self, httpx_mock):
        """Mock httpx.get() to return 200 with sample RSS XML bytes containing feed title, verify feed_meta() returns Feed with correct name."""
        from src.providers.rss_provider import RSSProvider
        from src.models import Feed

        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <description>A test feed</description>
        </channel>
        </rss>"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = rss_xml
        mock_response.headers = {"etag": "feed-etag", "last-modified": "feed-lm"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.providers.rss_provider.httpx.get", return_value=mock_response):
            with patch("src.providers.rss_provider.feedparser.parse") as mock_parse:
                mock_parsed = MagicMock()
                mock_parsed.feed = {"title": "Test Feed"}
                mock_parse.return_value = mock_parsed

                provider = RSSProvider()
                result = provider.feed_meta("https://example.com/feed.xml")

                assert isinstance(result, Feed)
                assert result.name == "Test Feed"
                assert result.url == "https://example.com/feed.xml"
                assert result.etag == "feed-etag"


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

    def test_github_release_provider_crawl_success(self):
        """Mock PyGithub client and get_repo()/get_latest_release() to return mock release."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        # Mock release object
        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"
        mock_release.name = "Release 1.0.0"
        mock_release.body = "Release notes for v1.0.0"
        mock_release.html_url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_release.published_at.isoformat = MagicMock(return_value="2024-01-15T10:30:00")

        # Mock repo
        mock_repo = MagicMock()
        mock_repo.get_latest_release = MagicMock(return_value=mock_release)

        # Mock client
        mock_client = MagicMock()
        mock_client.get_repo = MagicMock(return_value=mock_repo)

        with patch("src.providers.github_release_provider._get_github_client", return_value=mock_client):
            with patch("src.utils.github.parse_github_url", return_value=("owner", "repo")):
                provider = GitHubReleaseProvider()
                result = provider.crawl("https://github.com/owner/repo")

                assert len(result) == 1
                release_data = result[0]
                assert release_data["tag_name"] == "v1.0.0"
                assert release_data["name"] == "Release 1.0.0"
                assert release_data["body"] == "Release notes for v1.0.0"
                assert release_data["html_url"] == "https://github.com/owner/repo/releases/tag/v1.0.0"
                assert release_data["published_at"] == "2024-01-15T10:30:00"

    @pytest.mark.asyncio
    async def test_github_release_provider_crawl_async_success(self):
        """Mock asyncio.to_thread to verify crawl_async() runs crawl in thread pool."""
        from src.providers.github_release_provider import GitHubReleaseProvider

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            # Mock return value for to_thread (crawl result)
            mock_release_data = [{
                "tag_name": "v2.0.0",
                "name": "Release 2.0.0",
                "body": "Notes for v2",
                "html_url": "https://github.com/owner/repo/releases/tag/v2.0.0",
                "published_at": "2024-02-01T00:00:00",
            }]
            mock_to_thread.return_value = mock_release_data

            provider = GitHubReleaseProvider()
            result = await provider.crawl_async("https://github.com/owner/repo")

            # Verify to_thread was called with self.crawl and url
            mock_to_thread.assert_called_once()
            call_args = mock_to_thread.call_args
            assert call_args[0][0] == provider.crawl
            assert call_args[0][1] == "https://github.com/owner/repo"
            assert result.entries == mock_release_data

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
        result = provider.parse(mock_raw)

        assert isinstance(result, dict)
        assert result["title"] == "v1.0"
        assert result["link"] == "https://github.com/owner/repo/releases/tag/v1.0"
        assert result["guid"] == "v1.0"
        assert result["pub_date"] == "2024-01-01T00:00:00"
        assert result["description"] == "Release notes"
        assert result["content"] is None


# =============================================================================
# ProviderRegistry Tests
# =============================================================================

class TestProviderRegistry:
    """Tests for ProviderRegistry module-level functions."""

    def test_provider_registry_discover_matching(self):
        """Call discover('https://github.com/owner/repo') which should match GitHubReleaseProvider."""
        import src.providers as providers

        matched = providers.discover("https://github.com/owner/repo")
        assert len(matched) > 0
        # Find GitHubReleaseProvider in matched list
        provider_names = [p.__class__.__name__ for p in matched]
        assert "GitHubReleaseProvider" in provider_names

    def test_provider_registry_discover_multiple(self):
        """For a GitHub URL, verify discover() returns providers sorted by priority descending."""
        import src.providers as providers

        matched = providers.discover("https://github.com/owner/repo")
        assert len(matched) >= 1
        # Verify sorted by priority descending
        priorities = [p.priority() for p in matched]
        assert priorities == sorted(priorities, reverse=True)
        # GitHubReleaseProvider should be first (priority 200 > RSSProvider 50)
        assert matched[0].__class__.__name__ == "GitHubReleaseProvider"

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
        """Call discover('https://github.com/owner/repo') which matches GitHubReleaseProvider."""
        import src.providers as providers

        matched = providers.discover("https://github.com/owner/repo")
        assert len(matched) >= 1
        assert matched[0].__class__.__name__ == "GitHubReleaseProvider"

    def test_provider_registry_get_all_providers(self):
        """Verify get_all_providers() returns list of providers sorted by priority descending."""
        import src.providers as providers

        all_providers = providers.get_all_providers()
        assert len(all_providers) > 0
        # Verify sorted by priority descending
        priorities = [p.priority() for p in all_providers]
        assert priorities == sorted(priorities, reverse=True)
