"""Integration tests for CLI commands using CliRunner."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.models import Feed
from src.storage.sqlite import add_feed, init_db, store_article, upsert_feed


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


class TestFeedGroupCommands:
    """Tests for feed group functionality: feed list --group filter."""

    def test_feed_list_filter_by_group(self, cli_runner, initialized_db):
        """feed list --group <name> filters feeds to exact group match."""
        # Add feeds with different groups
        feed_ai = Feed(
            id="group-filter-ai",
            name="AI News",
            url="https://example.com/ai.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group="AI",
        )
        feed_llm = Feed(
            id="group-filter-llm",
            name="LLM News",
            url="https://example.com/llm.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
            group="LLM",
        )
        feed_tech = Feed(
            id="group-filter-tech",
            name="Tech News",
            url="https://example.com/tech.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-03T00:00:00+00:00",
            group="Tech",
        )
        upsert_feed(feed_ai)
        upsert_feed(feed_llm)
        upsert_feed(feed_tech)

        # Filter by AI group
        result = cli_runner.invoke(cli, ["feed", "list", "--group", "AI"])
        assert result.exit_code == 0
        assert "AI News" in result.output
        assert "LLM News" not in result.output
        assert "Tech News" not in result.output

    def test_feed_list_filter_ungrouped(self, cli_runner, initialized_db):
        """feed list --group "" and --group none shows ungrouped feeds."""
        # Add grouped and ungrouped feeds
        feed_grouped = Feed(
            id="grouped-feed",
            name="Grouped Feed",
            url="https://example.com/grouped.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group="AI",
        )
        feed_ungrouped = Feed(
            id="ungrouped-feed",
            name="Ungrouped Feed",
            url="https://example.com/ungrouped.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
            group=None,
        )
        upsert_feed(feed_grouped)
        upsert_feed(feed_ungrouped)

        # Filter by empty string
        result = cli_runner.invoke(cli, ["feed", "list", "--group", ""])
        assert result.exit_code == 0
        assert "Ungrouped" in result.output
        assert "Grouped Feed" not in result.output

        # Filter by "none"
        result = cli_runner.invoke(cli, ["feed", "list", "--group", "none"])
        assert result.exit_code == 0
        assert "Ungrouped" in result.output
        assert "Grouped Feed" not in result.output

    def test_feed_list_multiple_groups_all_shown(self, cli_runner, initialized_db):
        """feed list shows all groups when no filter applied."""
        feed1 = Feed(
            id="multi-group-1",
            name="Group 1 Feed",
            url="https://example.com/mg1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group="Group1",
        )
        feed2 = Feed(
            id="multi-group-2",
            name="Group 2 Feed",
            url="https://example.com/mg2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
            group="Group2",
        )
        upsert_feed(feed1)
        upsert_feed(feed2)

        # No filter - all feeds shown
        result = cli_runner.invoke(cli, ["feed", "list"])
        assert result.exit_code == 0
        assert "Group 1" in result.output
        assert "Group 2" in result.output

    def test_feed_list_group_verbose(self, cli_runner, initialized_db):
        """feed list --verbose shows group column."""
        feed = Feed(
            id="verbose-group-feed",
            name="Verbose Feed",
            url="https://example.com/verbose.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group="VerboseGroup",
        )
        upsert_feed(feed)

        result = cli_runner.invoke(cli, ["feed", "list", "--verbose"])
        assert result.exit_code == 0
        assert "VerboseGroup" in result.output
        assert "Verbose Feed" in result.output


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


class TestArticleGroupCommands:
    """Tests for article commands with --groups filter."""

    def _create_grouped_feeds_with_articles(self, initialized_db):
        """Helper to create feeds with groups and articles."""
        feeds = [
            Feed(
                id="article-group-ai",
                name="AI News",
                url="https://ai.example.com/feed.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                group="AI",
            ),
            Feed(
                id="article-group-llm",
                name="LLM News",
                url="https://llm.example.com/feed.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-02T00:00:00+00:00",
                group="LLM",
            ),
            Feed(
                id="article-group-tech",
                name="Tech News",
                url="https://tech.example.com/feed.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-03T00:00:00+00:00",
                group="Tech",
            ),
            Feed(
                id="article-group-none",
                name="Ungrouped News",
                url="https://none.example.com/feed.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-04T00:00:00+00:00",
                group=None,
            ),
        ]
        for feed in feeds:
            upsert_feed(feed)

        # Add articles
        articles = [
            (
                "ai-article-1",
                "article-group-ai",
                "AI and Machine Learning",
                "AI content",
            ),
            ("ai-article-2", "article-group-ai", "Deep Learning News", "DL content"),
            ("llm-article-1", "article-group-llm", "LLM like GPT-4", "LLM content"),
            ("tech-article-1", "article-group-tech", "Python Tutorial", "Tech content"),
            (
                "none-article-1",
                "article-group-none",
                "Random Article",
                "Ungrouped content",
            ),
        ]
        for article_id, feed_id, title, desc in articles:
            store_article(
                guid=article_id,
                title=title,
                content=f"<p>{desc}</p>",
                link=f"https://{feed_id}.com/article",
                feed_id=feed_id,
                published_at="2024-01-15T10:00:00+00:00",
            )

    def test_article_list_with_groups(self, cli_runner, initialized_db):
        """article list --groups AI filters to only AI group articles."""
        self._create_grouped_feeds_with_articles(initialized_db)

        result = cli_runner.invoke(cli, ["article", "list", "--groups", "AI"])
        assert result.exit_code == 0
        # Should show AI articles
        assert "AI" in result.output
        # Should not show LLM or Tech articles (table may wrap names)
        # The ungrouped article should not appear
        assert "LLM" not in result.output
        assert "Tech" not in result.output

    def test_article_list_with_multiple_groups(self, cli_runner, initialized_db):
        """article list --groups AI,LLM shows articles from either group."""
        self._create_grouped_feeds_with_articles(initialized_db)

        result = cli_runner.invoke(cli, ["article", "list", "--groups", "AI,LLM"])
        assert result.exit_code == 0
        assert "AI" in result.output
        assert "LLM" in result.output
        assert "Tech" not in result.output

    def test_article_list_groups_excludes_ungrouped(self, cli_runner, initialized_db):
        """article list --groups AI excludes articles from ungrouped feeds."""
        self._create_grouped_feeds_with_articles(initialized_db)

        result = cli_runner.invoke(cli, ["article", "list", "--groups", "AI"])
        assert result.exit_code == 0
        assert "Random" not in result.output  # Ungrouped article excluded

    def test_article_search_with_groups(self, cli_runner, initialized_db):
        """search AI --groups AI filters FTS results to AI group."""
        self._create_grouped_feeds_with_articles(initialized_db)

        result = cli_runner.invoke(cli, ["search", "AI", "--groups", "AI"])
        assert result.exit_code == 0
        assert "AI" in result.output


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


class TestInfoCommands:
    """Tests for info CLI command: info --version, --config, --storage, --json."""

    def test_info_all_sections(self, cli_runner, initialized_db):
        """feedship info shows all sections (version, config, storage)."""
        result = cli_runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "feedship v" in result.output
        assert "Config:" in result.output
        assert "Articles:" in result.output

    def test_info_version_only(self, cli_runner, initialized_db):
        """feedship info --version shows version only."""
        result = cli_runner.invoke(cli, ["info", "--version"])
        assert result.exit_code == 0
        assert "feedship v" in result.output
        assert "Config:" not in result.output
        assert "Articles:" not in result.output

    def test_info_config_only(self, cli_runner, initialized_db):
        """feedship info --config shows config path and values."""
        result = cli_runner.invoke(cli, ["info", "--config"])
        assert result.exit_code == 0
        assert "Config:" in result.output
        assert "Articles:" not in result.output
        assert (
            "version:" in result.output.lower() or "timezone:" in result.output.lower()
        )

    def test_info_storage_only(self, cli_runner, initialized_db):
        """feedship info --storage shows storage path and stats."""
        result = cli_runner.invoke(cli, ["info", "--storage"])
        assert result.exit_code == 0
        assert "Articles:" in result.output
        assert "feedship v" not in result.output

    def test_info_json_output(self, cli_runner, initialized_db):
        """feedship info --json outputs valid JSON."""
        result = cli_runner.invoke(cli, ["info", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "version" in data
        assert "config_path" in data
        assert "config" in data
        assert "storage_path" in data
        assert "storage" in data

    def test_info_json_with_filters(self, cli_runner, initialized_db):
        """feedship info --config --json outputs filtered JSON."""
        result = cli_runner.invoke(cli, ["info", "--config", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "config_path" in data
        assert "config" in data
        assert "version" not in data
        assert "storage" not in data

    def test_info_combined_filters(self, cli_runner, initialized_db):
        """feedship info --version --config shows version and config only."""
        result = cli_runner.invoke(cli, ["info", "--version", "--config"])
        assert result.exit_code == 0
        assert "feedship v" in result.output
        assert "Config:" in result.output
        assert "Articles:" not in result.output
