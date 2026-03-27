"""Integration tests for CLI commands using CliRunner."""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from src.cli import cli
from src.storage.sqlite import init_db, add_feed, store_article
from src.models import Feed


class TestFeedCommands:
    """Tests for feed CLI commands: feed add, feed list, feed remove."""

    def test_feed_add_success(self, cli_runner, initialized_db):
        """feed add <url> succeeds and outputs 'Added feed'."""
        # Mock RSS feed response using patch like other tests in this project
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <description>Test feed</description>
            <item>
                <title>Article 1</title>
                <link>https://example.com/article1</link>
                <guid>article-1-guid</guid>
                <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
            </item>
        </channel>
        </rss>"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = rss_xml
        mock_response.headers = {"content-type": "application/rss+xml"}

        with patch("src.providers.rss_provider.httpx.get", return_value=mock_response):
            result = cli_runner.invoke(cli, ['feed', 'add', 'https://example.com/feed.xml'])
        assert result.exit_code == 0
        assert 'Added feed' in result.output

    def test_feed_add_duplicate_returns_error(self, cli_runner, initialized_db):
        """feed add with duplicate URL returns exit code 1."""
        # Mock RSS feed response using patch
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <item>
                <title>Article 1</title>
                <link>https://example.com/article1</link>
                <guid>article-1-guid</guid>
            </item>
        </channel>
        </rss>"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = rss_xml
        mock_response.headers = {"content-type": "application/rss+xml"}

        with patch("src.providers.rss_provider.httpx.get", return_value=mock_response):
            # Add feed first
            cli_runner.invoke(cli, ['feed', 'add', 'https://example.com/dup.xml'])
            # Try to add same URL again - duplicate detection happens after successful fetch
            result = cli_runner.invoke(cli, ['feed', 'add', 'https://example.com/dup.xml'])
        assert result.exit_code == 1
        assert 'Error' in result.output

    def test_feed_list_empty(self, cli_runner, initialized_db):
        """feed list with no feeds outputs 'No feeds subscribed'."""
        result = cli_runner.invoke(cli, ['feed', 'list'])
        assert result.exit_code == 0
        assert 'No feeds subscribed' in result.output

    def test_feed_list_with_feeds(self, cli_runner, initialized_db):
        """feed list shows feed names when feeds exist."""
        # Add feeds via storage
        feed1 = Feed(
            id="feed-list-1",
            name="Test Feed 1",
            url="https://example.com/feed1.xml",
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="feed-list-2",
            name="Test Feed 2",
            url="https://example.com/feed2.xml",
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at="2024-01-02T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        result = cli_runner.invoke(cli, ['feed', 'list'])
        assert result.exit_code == 0
        assert 'Test Feed 1' in result.output
        assert 'Test Feed 2' in result.output

    def test_feed_remove_success(self, cli_runner, initialized_db):
        """feed remove <id> removes feed and outputs 'Removed feed'."""
        # Mock RSS feed response using patch
        rss_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test Feed</title>
            <link>https://example.com</link>
            <item>
                <title>Article 1</title>
                <link>https://example.com/article1</link>
                <guid>article-1-guid</guid>
            </item>
        </channel>
        </rss>"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = rss_xml
        mock_response.headers = {"content-type": "application/rss+xml"}

        with patch("src.providers.rss_provider.httpx.get", return_value=mock_response):
            # Add feed first
            cli_runner.invoke(cli, ['feed', 'add', 'https://example.com/remove.xml'])
            # Get the feed ID from the database
            from src.storage.sqlite import list_feeds
            feeds = list_feeds()
            feed_id = feeds[0].id if feeds else None
            result = cli_runner.invoke(cli, ['feed', 'remove', feed_id])
        assert result.exit_code == 0
        assert 'Removed feed' in result.output

    def test_feed_remove_not_found(self, cli_runner, initialized_db):
        """feed remove with non-existent ID returns exit code 1 and 'not found'."""
        result = cli_runner.invoke(cli, ['feed', 'remove', 'non-existent-id'])
        assert result.exit_code == 1
        assert 'not found' in result.output.lower()


class TestArticleCommands:
    """Tests for article CLI commands: article list, article view, article search, article tag."""

    def test_article_list_empty(self, cli_runner, initialized_db):
        """article list with no articles outputs 'No articles found'."""
        result = cli_runner.invoke(cli, ['article', 'list'])
        assert result.exit_code == 0
        assert 'No articles found' in result.output

    def test_article_list_with_articles(self, cli_runner, initialized_db):
        """article list shows article title when articles exist."""
        # Add feed and article via storage
        feed = Feed(
            id="article-list-feed",
            name="Article List Feed",
            url="https://example.com/article-list.xml",
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)
        store_article(
            guid="article-list-guid",
            title="Article List Test Title",
            content="<p>Content here</p>",
            link="https://example.com/article-list",
            feed_id="article-list-feed",
            pub_date="2024-01-15T10:00:00+00:00",
        )

        result = cli_runner.invoke(cli, ['article', 'list'])
        assert result.exit_code == 0
        assert 'Article List Test Title' in result.output

    def test_article_view_success(self, cli_runner, initialized_db):
        """article view <id> shows article detail with title."""
        # Add feed and article via storage
        feed = Feed(
            id="article-view-feed",
            name="Article View Feed",
            url="https://example.com/article-view.xml",
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)
        article_id = store_article(
            guid="article-view-guid",
            title="Article View Test Title",
            content="<p>Full content here</p>",
            link="https://example.com/article-view",
            feed_id="article-view-feed",
            pub_date="2024-01-15T10:00:00+00:00",
        )

        result = cli_runner.invoke(cli, ['article', 'view', article_id[:8]])
        assert result.exit_code == 0
        assert 'Article View Test Title' in result.output

    def test_article_view_not_found(self, cli_runner, initialized_db):
        """article view with non-existent ID returns exit code 1 and 'not found'."""
        result = cli_runner.invoke(cli, ['article', 'view', 'non-existent-id'])
        assert result.exit_code == 1
        assert 'not found' in result.output.lower()

    def test_article_search_found(self, cli_runner, initialized_db):
        """search <query> shows article title when matches found."""
        # Add feed and article via storage
        feed = Feed(
            id="article-search-feed",
            name="Article Search Feed",
            url="https://example.com/article-search.xml",
            etag=None,
            last_modified=None,
            last_fetched=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)
        store_article(
            guid="article-search-guid",
            title="Python Tutorial Article",
            content="Learn Python programming",
            link="https://example.com/article-search",
            feed_id="article-search-feed",
            pub_date="2024-01-15T10:00:00+00:00",
        )

        result = cli_runner.invoke(cli, ['search', 'Python'])
        assert result.exit_code == 0
        assert 'Python Tutorial Article' in result.output

    def test_article_search_not_found(self, cli_runner, initialized_db):
        """search with no matches outputs 'No articles found'."""
        # Use query without hyphens since FTS5 interprets hyphens as exclusion operators
        result = cli_runner.invoke(cli, ['search', 'nonexistent query xyz'])
        assert result.exit_code == 0
        assert 'No articles found' in result.output

