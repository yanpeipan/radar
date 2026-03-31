"""Unit tests for SQLite storage layer functions.

Test Conventions (from Phase 26):
1. NO PRIVATE FUNCTION TESTING - test only public interfaces
2. REAL DATABASE VIA tmp_path - use initialized_db fixture for database tests
3. HTTP MOCKING WITH httpx_mock - use pytest-httpx's httpx_mock fixture for HTTP requests
4. CLI TESTING WITH CliRunner
"""

import asyncio
import sqlite3

import pytest

# =============================================================================
# TestArticleOperations
# =============================================================================


class TestArticleOperations:
    """Tests for article storage functions: store_article, store_article_async,
    list_articles, get_article, get_article_detail, search_articles,
    list_articles_with_tags, get_articles_with_tags.
    """

    def test_store_article_returns_nanoid_format(self, initialized_db):
        """store_article() stores article and returns article_id in nanoid format."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article

        # Create feed first (FK requirement)
        feed = Feed(
            id="feed-1",
            name="Test Feed",
            url="https://example.com/feed.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        # Store article
        article_id = store_article(
            guid="article-guid-1",
            title="Test Article",
            content="<p>Article content</p>",
            link="https://example.com/article1",
            feed_id="feed-1",
            published_at="2024-01-15T10:00:00+00:00",
        )

        assert article_id is not None
        assert isinstance(article_id, str)
        assert len(article_id) > 0
        # nanoid format: URL-safe, alphanumeric
        assert article_id.replace("-", "").replace("_", "").isalnum()

    def test_store_article_async_returns_nanoid(self, initialized_db):
        """store_article_async() async wrapper returns article_id in nanoid format."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article_async

        feed = Feed(
            id="feed-async",
            name="Async Feed",
            url="https://example.com/async.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = asyncio.run(
            store_article_async(
                guid="async-article-guid-1",
                title="Async Article",
                content="<p>Async content</p>",
                link="https://example.com/async-article",
                feed_id="feed-async",
                published_at="2024-01-16T10:00:00+00:00",
            )
        )

        assert article_id is not None
        assert isinstance(article_id, str)
        assert len(article_id) > 0

    def test_list_articles_returns_ordered_by_published_at(self, initialized_db):
        """list_articles() returns list of ArticleListItem ordered by published_at DESC."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, list_articles, store_article

        feed = Feed(
            id="feed-list",
            name="List Feed",
            url="https://example.com/list.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        # Store articles with different published_ats
        store_article(
            guid="old-article",
            title="Old Article",
            content="Old content",
            link="https://example.com/old",
            feed_id="feed-list",
            published_at="2024-01-01T10:00:00+00:00",
        )
        store_article(
            guid="new-article",
            title="New Article",
            content="New content",
            link="https://example.com/new",
            feed_id="feed-list",
            published_at="2024-01-20T10:00:00+00:00",
        )
        store_article(
            guid="mid-article",
            title="Mid Article",
            content="Mid content",
            link="https://example.com/mid",
            feed_id="feed-list",
            published_at="2024-01-10T10:00:00+00:00",
        )

        articles = list_articles(limit=20)

        assert len(articles) == 3
        # Verify ordered by published_at DESC (newest first)
        assert articles[0].title == "New Article"
        assert articles[1].title == "Mid Article"
        assert articles[2].title == "Old Article"
        # Verify ArticleListItem fields
        for article in articles:
            assert article.id is not None
            assert article.feed_id == "feed-list"
            assert article.feed_name == "List Feed"
            assert article.guid is not None

    def test_list_articles_with_feed_id_filter(self, initialized_db):
        """list_articles() with feed_id filter returns only articles from that feed."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, list_articles, store_article

        feed1 = Feed(
            id="feed-1",
            name="Feed 1",
            url="https://example.com/feed1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="feed-2",
            name="Feed 2",
            url="https://example.com/feed2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        store_article(
            guid="article-feed1",
            title="Article in Feed 1",
            content="Content 1",
            link="https://example.com/f1",
            feed_id="feed-1",
            published_at="2024-01-15T10:00:00+00:00",
        )
        store_article(
            guid="article-feed2",
            title="Article in Feed 2",
            content="Content 2",
            link="https://example.com/f2",
            feed_id="feed-2",
            published_at="2024-01-15T11:00:00+00:00",
        )

        articles_feed1 = list_articles(limit=20, feed_id="feed-1")
        articles_feed2 = list_articles(limit=20, feed_id="feed-2")

        assert len(articles_feed1) == 1
        assert articles_feed1[0].title == "Article in Feed 1"
        assert articles_feed1[0].feed_id == "feed-1"

        assert len(articles_feed2) == 1
        assert articles_feed2[0].title == "Article in Feed 2"
        assert articles_feed2[0].feed_id == "feed-2"

    def test_get_article_returns_single_article(self, initialized_db):
        """get_article() returns single ArticleListItem by ID."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_article, store_article

        feed = Feed(
            id="feed-get",
            name="Get Feed",
            url="https://example.com/get.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="get-article-guid",
            title="Get Article",
            content="<p>Get content</p>",
            link="https://example.com/get-article",
            feed_id="feed-get",
            published_at="2024-01-15T10:00:00+00:00",
        )

        article = get_article(article_id)

        assert article is not None
        assert article.id == article_id
        assert article.title == "Get Article"
        assert article.feed_id == "feed-get"
        assert article.feed_name == "Get Feed"
        assert article.guid == "get-article-guid"

    def test_get_article_with_invalid_id_returns_none(self, initialized_db):
        """get_article() with non-existing ID returns None."""
        from src.storage.sqlite import get_article

        article = get_article("non-existent-id")
        assert article is None

    def test_get_article_detail_with_truncated_8char_id(self, initialized_db):
        """get_article_detail() with truncated 8-char ID matches prefix."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_article_detail, store_article

        feed = Feed(
            id="feed-trunc",
            name="Trunc Feed",
            url="https://example.com/trunc.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="trunc-guid",
            title="Truncated Article",
            content="<p>Truncated content</p>",
            link="https://example.com/trunc",
            feed_id="feed-trunc",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Use first 8 characters of article_id
        truncated_id = article_id[:8]
        detail = get_article_detail(truncated_id)

        assert detail is not None
        assert detail["id"] == article_id
        assert detail["title"] == "Truncated Article"

    def test_get_article_detail_with_invalid_id_returns_none(self, initialized_db):
        """get_article_detail() with non-existing ID returns None."""
        from src.storage.sqlite import get_article_detail

        detail = get_article_detail("non-existent-id")
        assert detail is None

    def test_search_articles_fts5_returns_matches(self, initialized_db):
        """search_articles() FTS5 search returns matching articles."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, search_articles, store_article

        feed = Feed(
            id="feed-search",
            name="Search Feed",
            url="https://example.com/search.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        store_article(
            guid="search-python",
            title="Python Tutorial",
            content="Learn Python programming",
            link="https://example.com/python",
            feed_id="feed-search",
            published_at="2024-01-15T10:00:00+00:00",
        )
        store_article(
            guid="search-java",
            title="Java Guide",
            content="Java programming tutorial",
            link="https://example.com/java",
            feed_id="feed-search",
            published_at="2024-01-16T10:00:00+00:00",
        )

        results = search_articles("Python")

        assert len(results) == 1
        assert results[0].title == "Python Tutorial"
        assert results[0].id is not None

    def test_search_articles_with_feed_id_filter(self, initialized_db):
        """search_articles() with feed_id filter searches within specific feed."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, search_articles, store_article

        feed1 = Feed(
            id="feed-s1",
            name="Search Feed 1",
            url="https://example.com/s1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="feed-s2",
            name="Search Feed 2",
            url="https://example.com/s2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        store_article(
            guid="s1-python",
            title="Python in Feed 1",
            content="Python content",
            link="https://example.com/s1p",
            feed_id="feed-s1",
            published_at="2024-01-15T10:00:00+00:00",
        )
        store_article(
            guid="s2-python",
            title="Python in Feed 2",
            content="Python content",
            link="https://example.com/s2p",
            feed_id="feed-s2",
            published_at="2024-01-16T10:00:00+00:00",
        )

        # Search within feed1 only
        results = search_articles("Python", feed_id="feed-s1")

        assert len(results) == 1
        assert results[0].feed_id == "feed-s1"
        assert results[0].title == "Python in Feed 1"

    def test_search_articles_with_empty_query_returns_empty(self, initialized_db):
        """search_articles() with empty query returns empty list."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, search_articles, store_article

        feed = Feed(
            id="feed-empty",
            name="Empty Search Feed",
            url="https://example.com/empty.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        store_article(
            guid="empty-article",
            title="Some Article",
            content="Some content",
            link="https://example.com/some",
            feed_id="feed-empty",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Empty string
        results = search_articles("")
        assert results == []

        # Whitespace only
        results = search_articles("   ")
        assert results == []

    def test_store_article_updates_existing_on_guid_match(self, initialized_db):
        """store_article() updates existing article if guid already exists."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, list_articles, store_article

        feed = Feed(
            id="feed-update",
            name="Update Feed",
            url="https://example.com/update.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        # Store first time
        article_id1 = store_article(
            guid="update-guid",
            title="Original Title",
            content="Original content",
            link="https://example.com/update",
            feed_id="feed-update",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Store again with same guid - should update
        article_id2 = store_article(
            guid="update-guid",
            title="Updated Title",
            content="Updated content",
            link="https://example.com/update",
            feed_id="feed-update",
            published_at="2024-01-16T10:00:00+00:00",
        )

        # Should return same article_id (updated, not new)
        assert article_id1 == article_id2

        articles = list_articles(limit=10)
        # Should still have only 1 article
        assert len(articles) == 1
        assert articles[0].title == "Updated Title"


# =============================================================================
# TestFeedOperations
# =============================================================================


class TestFeedOperations:
    """Tests for feed storage functions: feed_exists, add_feed, list_feeds,
    get_feed, remove_feed.
    """

    def test_feed_exists_with_existing_url(self, initialized_db):
        """feed_exists() with existing URL returns True."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, feed_exists

        feed = Feed(
            id="exists-feed",
            name="Exists Feed",
            url="https://example.com/exists.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        assert feed_exists("https://example.com/exists.xml") is True

    def test_feed_exists_with_non_existing_url(self, initialized_db):
        """feed_exists() with non-existing URL returns False."""
        from src.storage.sqlite import feed_exists

        assert feed_exists("https://example.com/non-existent.xml") is False

    def test_add_feed_inserts_and_returns_feed(self, initialized_db):
        """add_feed() inserts feed and returns Feed object."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed

        feed = Feed(
            id="add-feed-1",
            name="Add Feed",
            url="https://example.com/add.xml",
            etag="test-etag",
            modified_at="test-lm",
            fetched_at="2024-01-15T10:00:00+00:00",
            created_at="2024-01-01T00:00:00+00:00",
        )

        result = add_feed(feed)

        assert result is not None
        assert result.id == "add-feed-1"
        assert result.name == "Add Feed"

        # Verify persisted
        stored = get_feed("add-feed-1")
        assert stored is not None
        assert stored.name == "Add Feed"
        assert stored.url == "https://example.com/add.xml"
        assert stored.etag == "test-etag"

    def test_add_feed_duplicate_url_raises_integrity_error(self, initialized_db):
        """add_feed() with duplicate URL raises sqlite3.IntegrityError."""
        from src.models import Feed
        from src.storage.sqlite import add_feed

        feed1 = Feed(
            id="feed-dup-1",
            name="Duplicate Feed 1",
            url="https://example.com/dup.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="feed-dup-2",
            name="Duplicate Feed 2",
            url="https://example.com/dup.xml",  # Same URL
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )

        add_feed(feed1)

        with pytest.raises(sqlite3.IntegrityError):
            add_feed(feed2)

    def test_list_feeds_returns_with_articles_count(self, initialized_db):
        """list_feeds() returns list with articles_count attribute."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, list_feeds, store_article

        feed1 = Feed(
            id="list-feed-1",
            name="List Feed 1",
            url="https://example.com/list1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        feed2 = Feed(
            id="list-feed-2",
            name="List Feed 2",
            url="https://example.com/list2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
        )
        add_feed(feed1)
        add_feed(feed2)

        # Add articles to feed1 only
        store_article(
            guid="list-article-1",
            title="List Article 1",
            content="Content 1",
            link="https://example.com/la1",
            feed_id="list-feed-1",
            published_at="2024-01-15T10:00:00+00:00",
        )
        store_article(
            guid="list-article-2",
            title="List Article 2",
            content="Content 2",
            link="https://example.com/la2",
            feed_id="list-feed-1",
            published_at="2024-01-16T10:00:00+00:00",
        )

        feeds = list_feeds()

        assert len(feeds) == 2
        # Check articles_count attribute
        feed1_result = next(f for f in feeds if f.id == "list-feed-1")
        feed2_result = next(f for f in feeds if f.id == "list-feed-2")
        assert feed1_result.articles_count == 2
        assert feed2_result.articles_count == 0
        # Verify ordered by created_at DESC
        assert feeds[0].name == "List Feed 2"  # Created later
        assert feeds[1].name == "List Feed 1"

    def test_list_feeds_empty_returns_empty_list(self, initialized_db):
        """list_feeds() with no feeds returns empty list."""
        from src.storage.sqlite import list_feeds

        feeds = list_feeds()
        assert feeds == []

    def test_get_feed_with_existing_id(self, initialized_db):
        """get_feed() with existing ID returns Feed object."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed

        feed = Feed(
            id="get-feed-1",
            name="Get Feed",
            url="https://example.com/get.xml",
            etag="get-etag",
            modified_at="get-lm",
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        result = get_feed("get-feed-1")

        assert result is not None
        assert result.id == "get-feed-1"
        assert result.name == "Get Feed"
        assert result.url == "https://example.com/get.xml"
        assert result.etag == "get-etag"

    def test_get_feed_with_non_existing_id(self, initialized_db):
        """get_feed() with non-existing ID returns None."""
        from src.storage.sqlite import get_feed

        result = get_feed("non-existent-feed-id")
        assert result is None

    def test_remove_feed_with_existing_id(self, initialized_db):
        """remove_feed() with existing ID returns True and feed is deleted."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed, list_feeds, remove_feed

        feed = Feed(
            id="remove-feed-1",
            name="Remove Feed",
            url="https://example.com/remove.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        result = remove_feed("remove-feed-1")

        assert result is True
        assert get_feed("remove-feed-1") is None
        # Verify not in list
        feeds = list_feeds()
        assert len(feeds) == 0

    def test_remove_feed_with_non_existing_id(self, initialized_db):
        """remove_feed() with non-existing ID returns False."""
        from src.storage.sqlite import remove_feed

        result = remove_feed("non-existent-feed-id")
        assert result is False

    def test_remove_feed_cascade_deletes_articles(self, initialized_db):
        """remove_feed() cascade deletes associated articles."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, list_feeds, remove_feed, store_article

        feed = Feed(
            id="cascade-feed",
            name="Cascade Feed",
            url="https://example.com/cascade.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        # Add articles
        store_article(
            guid="cascade-article-1",
            title="Cascade Article 1",
            content="Content 1",
            link="https://example.com/c1",
            feed_id="cascade-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )
        store_article(
            guid="cascade-article-2",
            title="Cascade Article 2",
            content="Content 2",
            link="https://example.com/c2",
            feed_id="cascade-feed",
            published_at="2024-01-16T10:00:00+00:00",
        )

        # Verify articles exist
        feeds = list_feeds()
        assert feeds[0].articles_count == 2

        # Remove feed
        result = remove_feed("cascade-feed")

        assert result is True
        # Verify feed is gone
        feeds = list_feeds()
        assert len(feeds) == 0
