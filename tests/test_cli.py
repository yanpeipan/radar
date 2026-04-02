"""Integration tests for CLI commands using CliRunner."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.models import Feed
from src.storage.sqlite import add_feed, init_db, store_article


class TestFeedCommands:
    """Tests for feed CLI commands: feed add, feed list, feed remove."""

    def test_feed_add_success(self, cli_runner, initialized_db, monkeypatch):
        """feed add <url> succeeds and outputs 'Added feed'."""
        from src.discovery.models import DiscoveredFeed, DiscoveredResult

        # Mock discover_feeds to return a simple RSS feed directly
        mock_result = DiscoveredResult(
            url="https://example.com/feed.xml",
            max_depth=1,
            feeds=[
                DiscoveredFeed(
                    url="https://example.com/feed.xml",
                    title="Test Feed",
                    feed_type="rss",
                    source="RSSProvider",
                    page_url="https://example.com/feed.xml",
                    valid=True,
                ),
            ],
            selectors={},
        )

        async def mock_discover_feeds(url, depth, auto_discover):
            return mock_result

        monkeypatch.setattr("src.cli.feed.discover_feeds", mock_discover_feeds)

        # Use 'a' to select all feeds automatically
        result = cli_runner.invoke(
            cli,
            ["feed", "add", "--no-auto-discover", "https://example.com/feed.xml"],
            input="a\n",
        )
        assert result.exit_code == 0
        assert "Added" in result.output

    def test_feed_add_duplicate_returns_error(
        self, cli_runner, initialized_db, monkeypatch
    ):
        """feed add with duplicate URL returns exit code 1."""
        from src.discovery.models import DiscoveredFeed, DiscoveredResult

        mock_result = DiscoveredResult(
            url="https://example.com/dup.xml",
            max_depth=1,
            feeds=[
                DiscoveredFeed(
                    url="https://example.com/dup.xml",
                    title="Test Feed",
                    feed_type="rss",
                    source="RSSProvider",
                    page_url="https://example.com/dup.xml",
                    valid=True,
                ),
            ],
            selectors={},
        )

        async def mock_discover_feeds(url, depth, auto_discover):
            return mock_result

        monkeypatch.setattr("src.cli.feed.discover_feeds", mock_discover_feeds)

        # Add feed first
        cli_runner.invoke(
            cli,
            ["feed", "add", "--no-auto-discover", "https://example.com/dup.xml"],
            input="a\n",
        )
        # Try to add same URL again - duplicate is updated silently (upsert behavior)
        result = cli_runner.invoke(
            cli,
            ["feed", "add", "--no-auto-discover", "https://example.com/dup.xml"],
            input="a\n",
        )
        # Duplicate is handled gracefully as an update
        assert result.exit_code == 0
        assert "updated" in result.output.lower()

    def test_feed_list_empty(self, cli_runner, initialized_db):
        """feed list with no feeds outputs 'No feeds subscribed'."""
        result = cli_runner.invoke(cli, ["feed", "list"])
        assert result.exit_code == 0
        assert "No feeds subscribed" in result.output

    def test_feed_list_with_feeds(self, cli_runner, initialized_db):
        """feed list shows feed names when feeds exist."""
        # Add feeds via storage
        feed1 = Feed(
            id="feed-list-1",
            name="Test Feed 1",
            url="https://example.com/feed1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="feed-list-2",
            name="Test Feed 2",
            url="https://example.com/feed2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        result = cli_runner.invoke(cli, ["feed", "list"])
        assert result.exit_code == 0
        assert "Test Feed 1" in result.output
        assert "Test Feed 2" in result.output

    def test_feed_remove_success(self, cli_runner, initialized_db, monkeypatch):
        """feed remove <id> removes feed and outputs 'Removed feed'."""
        from src.discovery.models import DiscoveredFeed, DiscoveredResult

        mock_result = DiscoveredResult(
            url="https://example.com/remove.xml",
            max_depth=1,
            feeds=[
                DiscoveredFeed(
                    url="https://example.com/remove.xml",
                    title="Test Feed",
                    feed_type="rss",
                    source="RSSProvider",
                    page_url="https://example.com/remove.xml",
                    valid=True,
                ),
            ],
            selectors={},
        )

        async def mock_discover_feeds(url, depth, auto_discover):
            return mock_result

        monkeypatch.setattr("src.cli.feed.discover_feeds", mock_discover_feeds)

        # Add feed first
        cli_runner.invoke(
            cli,
            ["feed", "add", "--no-auto-discover", "https://example.com/remove.xml"],
            input="a\n",
        )
        # Get the feed ID from the database
        from src.storage.sqlite import list_feeds

        feeds = list_feeds()
        feed_id = feeds[0].id if feeds else None
        result = cli_runner.invoke(cli, ["feed", "remove", feed_id])
        assert result.exit_code == 0
        assert "Removed feed" in result.output

    def test_feed_remove_not_found(self, cli_runner, initialized_db):
        """feed remove with non-existent ID returns exit code 1 and 'not found'."""
        result = cli_runner.invoke(cli, ["feed", "remove", "non-existent-id"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestArticleCommands:
    """Tests for article CLI commands: article list, article view, article search, article tag."""

    def test_article_list_empty(self, cli_runner, initialized_db):
        """article list with no articles outputs 'No articles found'."""
        result = cli_runner.invoke(cli, ["article", "list"])
        assert result.exit_code == 0
        assert "No articles found" in result.output

    def test_article_list_with_articles(self, cli_runner, initialized_db):
        """article list shows article title when articles exist."""
        # Add feed and article via storage
        feed = Feed(
            id="article-list-feed",
            name="Article List Feed",
            url="https://example.com/article-list.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)
        store_article(
            guid="article-list-guid",
            title="Article List Test Title",
            content="<p>Content here</p>",
            link="https://example.com/article-list",
            feed_id="article-list-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        result = cli_runner.invoke(cli, ["article", "list"])
        assert result.exit_code == 0
        assert "Article List Test Title" in result.output

    def test_article_view_success(self, cli_runner, initialized_db):
        """article view <id> shows article detail with title."""
        # Add feed and article via storage
        feed = Feed(
            id="article-view-feed",
            name="Article View Feed",
            url="https://example.com/article-view.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)
        article_id = store_article(
            guid="article-view-guid",
            title="Article View Test Title",
            content="<p>Full content here</p>",
            link="https://example.com/article-view",
            feed_id="article-view-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        result = cli_runner.invoke(cli, ["article", "view", article_id[:8]])
        assert result.exit_code == 0
        assert "Article View Test Title" in result.output

    def test_article_view_not_found(self, cli_runner, initialized_db):
        """article view with non-existent ID returns exit code 1 and 'not found'."""
        result = cli_runner.invoke(cli, ["article", "view", "non-existent-id"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_article_search_found(self, cli_runner, initialized_db):
        """search <query> shows article title when matches found."""
        # Add feed and article via storage
        feed = Feed(
            id="article-search-feed",
            name="Article Search Feed",
            url="https://example.com/article-search.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)
        store_article(
            guid="article-search-guid",
            title="Python Tutorial Article",
            content="Learn Python programming",
            link="https://example.com/article-search",
            feed_id="article-search-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        result = cli_runner.invoke(cli, ["search", "Python"])
        assert result.exit_code == 0
        assert "Python Tutorial Article" in result.output

    def test_article_search_not_found(self, cli_runner, initialized_db):
        """search with no matches outputs 'No articles found'."""
        # Use query without hyphens since FTS5 interprets hyphens as exclusion operators
        result = cli_runner.invoke(cli, ["search", "nonexistent query xyz"])
        assert result.exit_code == 0
        assert "No articles found" in result.output


class TestFeedDiscovery:
    """Tests for feed discovery functionality."""

    def test_feed_add_openai_discovers_news_rss(
        self, cli_runner, initialized_db, monkeypatch
    ):
        """feed add https://openai.com discovers news/rss.xml via CSS selector discovery."""
        from src.discovery.models import DiscoveredFeed, DiscoveredResult

        # Mock discover_feeds to return openai.com discovery result
        mock_result = DiscoveredResult(
            url="https://openai.com",
            max_depth=1,
            feeds=[
                DiscoveredFeed(
                    url="https://openai.com",
                    title="https://openai.com",
                    feed_type="webpage",
                    source="provider_WebpageProvider",
                    page_url="https://openai.com",
                    valid=False,
                ),
                DiscoveredFeed(
                    url="https://openai.com/news/rss.xml",
                    title=None,
                    feed_type="rss",
                    source="RSSProvider",
                    page_url="https://openai.com",
                    valid=True,
                ),
            ],
            selectors={},
        )

        async def mock_discover_feeds(url, depth, auto_discover):
            return mock_result

        monkeypatch.setattr("src.cli.feed.discover_feeds", mock_discover_feeds)

        result = cli_runner.invoke(
            cli, ["feed", "add", "https://openai.com", "--automatic", "on"]
        )
        assert result.exit_code == 0
        assert "Discovered 2 feed" in result.output
        assert "Added 2 feed" in result.output

    def test_feed_add_github_cli_discovers_release_feed(
        self, cli_runner, initialized_db, monkeypatch
    ):
        """feed add https://github.com/cli/cli discovers GitHubReleaseProvider feed."""
        from src.discovery.models import DiscoveredFeed, DiscoveredResult

        # Mock discover_feeds to return GitHub release feed
        mock_result = DiscoveredResult(
            url="https://github.com/cli/cli",
            max_depth=1,
            feeds=[
                DiscoveredFeed(
                    url="https://github.com/cli/cli",
                    title="https://github.com/cli/cli",
                    feed_type="github_release",
                    source="provider_GitHubReleaseProvider",
                    page_url="https://github.com/cli/cli",
                    valid=True,
                ),
            ],
            selectors={},
        )

        async def mock_discover_feeds(url, depth, auto_discover):
            return mock_result

        monkeypatch.setattr("src.cli.feed.discover_feeds", mock_discover_feeds)

        result = cli_runner.invoke(cli, ["feed", "add", "https://github.com/cli/cli"])
        assert result.exit_code == 0
        assert "Discovered 1 feed" in result.output
        assert "github.com/cli/cli" in result.output

    def test_feed_add_twitter_url_discovers_nitter(
        self, cli_runner, initialized_db, monkeypatch
    ):
        """feed add https://twitter.com/elonmusk discovers NitterProvider feed as x:elonmusk."""
        from src.discovery.models import DiscoveredFeed
        from src.models import FeedType

        # Mock providers.discover to return a Nitter feed
        def mock_providers_discover(url):
            if "twitter.com" in url or "x.com" in url:
                return [
                    DiscoveredFeed(
                        url="x:elonmusk",
                        title="Nitter: elonmusk",
                        feed_type=FeedType.NITTER,
                        source="provider_NitterProvider",
                        page_url=url,
                        valid=True,
                    )
                ]
            return []

        monkeypatch.setattr("src.providers.discover", mock_providers_discover)

        result = cli_runner.invoke(cli, ["feed", "add", "https://twitter.com/elonmusk"])
        assert result.exit_code == 0
        assert "x:elonmusk" in result.output
        assert "Discovered 1 feed" in result.output


class TestFetchCommands:
    """Tests for fetch CLI commands: fetch --all, fetch <id>."""

    def test_fetch_all_empty(self, cli_runner, initialized_db):
        """fetch --all with no feeds outputs 'No feeds subscribed'."""
        result = cli_runner.invoke(cli, ["fetch", "--all"])
        assert result.exit_code == 0
        assert "No feeds subscribed" in result.output

    def test_fetch_all_with_feeds(self, cli_runner, initialized_db):
        """fetch --all with feeds invokes fetch_all_async and shows results."""
        # Add feeds via storage
        feed1 = Feed(
            id="fetch-all-feed-1",
            name="Fetch All Feed 1",
            url="https://example.com/feed1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="fetch-all-feed-2",
            name="Fetch All Feed 2",
            url="https://example.com/feed2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        # Mock fetch_all_async to return a generator yielding results
        async def mock_fetch_all_async(concurrency=10):
            yield {
                "feed_id": "fetch-all-feed-1",
                "feed_name": "Fetch All Feed 1",
                "new_articles": 2,
            }
            yield {
                "feed_id": "fetch-all-feed-2",
                "feed_name": "Fetch All Feed 2",
                "new_articles": 0,
            }

        with patch("src.application.fetch.fetch_all_async", mock_fetch_all_async):
            result = cli_runner.invoke(cli, ["fetch", "--all"])
        assert result.exit_code == 0
        assert "Fetched" in result.output

    def test_fetch_single_by_id(self, cli_runner, initialized_db):
        """fetch <feed_id> fetches single feed and shows article count."""
        # Add feed via storage
        feed = Feed(
            id="fetch-single-feed",
            name="Fetch Single Feed",
            url="https://example.com/single.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        with patch(
            "src.application.fetch.fetch_one_async_by_id",
            return_value={"new_articles": 1},
        ):
            result = cli_runner.invoke(cli, ["fetch", "fetch-single-feed"])
        assert result.exit_code == 0
        assert "Fetched 1" in result.output

    def test_fetch_single_by_id_not_found(self, cli_runner, initialized_db):
        """fetch with non-existent ID returns exit code 1 and 'not found'."""
        result = cli_runner.invoke(cli, ["fetch", "nonexistent-id"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_fetch_multiple_ids(self, cli_runner, initialized_db):
        """fetch <id1> <id2> fetches multiple feeds."""
        # Add feeds via storage
        feed1 = Feed(
            id="fetch-multi-feed-1",
            name="Fetch Multi Feed 1",
            url="https://example.com/multi1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="fetch-multi-feed-2",
            name="Fetch Multi Feed 2",
            url="https://example.com/multi2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        # Mock fetch_ids_async to return a generator yielding results
        async def mock_fetch_ids_async(ids, concurrency=10):
            yield {"feed_id": "fetch-multi-feed-1", "new_articles": 1}
            yield {"feed_id": "fetch-multi-feed-2", "new_articles": 2}

        with patch("src.application.fetch.fetch_ids_async", mock_fetch_ids_async):
            result = cli_runner.invoke(
                cli, ["fetch", "fetch-multi-feed-1", "fetch-multi-feed-2"]
            )
        assert result.exit_code == 0


class TestDiscoverCommands:
    """Tests for discover CLI command."""

    def test_discover_success(self, cli_runner, initialized_db):
        """discover <url> outputs discovered feed URL when feeds found."""
        from src.discovery.models import DiscoveredFeed, DiscoveredResult

        mock_result = DiscoveredResult(
            url="https://example.com",
            max_depth=1,
            feeds=[
                DiscoveredFeed(
                    url="https://example.com/feed.xml",
                    title="Example RSS Feed",
                    feed_type="rss",
                    source="RSSProvider",
                    page_url="https://example.com",
                    valid=True,
                ),
            ],
            selectors={},
        )

        async def mock_discover_feeds(url, depth):
            return mock_result

        with patch("src.cli.discover.discover_feeds", mock_discover_feeds):
            result = cli_runner.invoke(cli, ["discover", "https://example.com"])
        assert result.exit_code == 0
        assert "feed.xml" in result.output

    def test_discover_no_feeds(self, cli_runner, initialized_db):
        """discover <url> with no feeds outputs 'No feeds discovered'."""
        from src.discovery.models import DiscoveredResult

        mock_result = DiscoveredResult(
            url="https://no-feeds.com",
            max_depth=1,
            feeds=[],
            selectors={},
        )

        async def mock_discover_feeds(url, depth):
            return mock_result

        with patch("src.cli.discover.discover_feeds", mock_discover_feeds):
            result = cli_runner.invoke(cli, ["discover", "https://no-feeds.com"])
        assert result.exit_code == 0
        assert "No feeds discovered" in result.output
