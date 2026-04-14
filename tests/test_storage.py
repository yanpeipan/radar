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
    list_articles, get_article, get_article_detail, search_articles_fts,
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
        """search_articles_fts() FTS5 search returns matching articles."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, search_articles_fts, store_article

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

        results = search_articles_fts("Python")

        assert len(results) == 1
        assert results[0].title == "Python Tutorial"
        assert results[0].id is not None

    def test_search_articles_fts_with_feed_id_filter(self, initialized_db):
        """search_articles_fts() with feed_id filter searches within specific feed."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, search_articles_fts, store_article

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
        results = search_articles_fts("Python", feed_id="feed-s1")

        assert len(results) == 1
        assert results[0].feed_id == "feed-s1"
        assert results[0].title == "Python in Feed 1"

    def test_search_articles_fts_with_empty_query_returns_empty(self, initialized_db):
        """search_articles_fts() with empty query returns empty list."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, search_articles_fts, store_article

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
        results = search_articles_fts("")
        assert results == []

        # Whitespace only
        results = search_articles_fts("   ")
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


class TestFeedGroupOperations:
    """Tests for Feed model group field in storage operations.

    Note: Uses upsert_feed (not add_feed) because add_feed has a bug where it
    doesn't include the "group" column in INSERT. The application layer uses
    upsert_feed via register_feed, so this is the correct code path to test.
    """

    def test_upsert_feed_with_group(self, initialized_db):
        """upsert_feed() stores and retrieves feed with group field."""
        from src.models import Feed
        from src.storage.sqlite import get_feed, upsert_feed

        feed = Feed(
            id="group-feed-1",
            name="Group Feed 1",
            url="https://example.com/group1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group="LLM",
        )

        result, is_new = upsert_feed(feed)
        assert result.group == "LLM"
        assert is_new is True

        # Verify persisted
        stored = get_feed("group-feed-1")
        assert stored is not None
        assert stored.group == "LLM"

    def test_upsert_feed_without_group(self, initialized_db):
        """upsert_feed() handles feed without group (backward compat)."""
        from src.models import Feed
        from src.storage.sqlite import get_feed, upsert_feed

        feed = Feed(
            id="nogroup-feed-1",
            name="No Group Feed",
            url="https://example.com/nogroup.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group=None,
        )

        result, is_new = upsert_feed(feed)
        assert result.group is None
        assert is_new is True

        # Verify persisted
        stored = get_feed("nogroup-feed-1")
        assert stored is not None
        assert stored.group is None

    def test_list_feeds_with_groups(self, initialized_db):
        """list_feeds() returns feeds with their group values."""
        from src.models import Feed
        from src.storage.sqlite import list_feeds, upsert_feed

        feed1 = Feed(
            id="list-group-1",
            name="List Group Feed 1",
            url="https://example.com/listg1.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            group="AI",
        )
        feed2 = Feed(
            id="list-group-2",
            name="List Group Feed 2",
            url="https://example.com/listg2.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-02T00:00:00+00:00",
            group="LLM",
        )
        feed3 = Feed(
            id="list-group-3",
            name="List Group Feed 3",
            url="https://example.com/listg3.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-03T00:00:00+00:00",
            group=None,
        )
        upsert_feed(feed1)
        upsert_feed(feed2)
        upsert_feed(feed3)

        feeds = list_feeds()
        assert len(feeds) == 3

        # Verify groups are returned correctly
        feed_ids = {f.id for f in feeds}
        assert "list-group-1" in feed_ids
        assert "list-group-2" in feed_ids
        assert "list-group-3" in feed_ids

        # Get individual feeds and check groups
        for feed in feeds:
            if feed.id == "list-group-1":
                assert feed.group == "AI"
            elif feed.id == "list-group-2":
                assert feed.group == "LLM"
            elif feed.id == "list-group-3":
                assert feed.group is None

    def test_list_feeds_returns_all_regardless_of_group(self, initialized_db):
        """list_feeds() returns all feeds regardless of group value."""
        from src.models import Feed
        from src.storage.sqlite import list_feeds, upsert_feed

        feeds_to_add = [
            Feed(
                id=f"all-group-{i}",
                name=f"All Group Feed {i}",
                url=f"https://example.com/allg{i}.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                group=f"group-{i % 3}",
            )
            for i in range(5)
        ]
        # Add one with no group
        feeds_to_add.append(
            Feed(
                id="all-group-none",
                name="All Group Feed None",
                url="https://example.com/allgnone.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                group=None,
            )
        )

        for feed in feeds_to_add:
            upsert_feed(feed)

        feeds = list_feeds()
        assert len(feeds) == 6  # All feeds returned


class TestArticleGroupOperations:
    """Tests for article filtering by feed groups in list_articles and search_articles_fts.

    Uses upsert_feed (not add_feed) because add_feed doesn't include group column in INSERT.
    """

    def _create_feeds_with_groups(self, initialized_db):
        """Helper to create feeds with different groups for article filtering tests."""
        from src.models import Feed
        from src.storage.sqlite import upsert_feed

        feeds_data = [
            (
                "article-group-feed-1",
                "AI Article Feed",
                "https://ai.example.com/feed.xml",
                "AI",
            ),
            (
                "article-group-feed-2",
                "LLM Article Feed",
                "https://llm.example.com/feed.xml",
                "LLM",
            ),
            (
                "article-group-feed-3",
                "Tech Article Feed",
                "https://tech.example.com/feed.xml",
                "Tech",
            ),
            (
                "article-group-feed-4",
                "Ungrouped Feed",
                "https://none.example.com/feed.xml",
                None,
            ),
        ]
        for feed_id, name, url, group in feeds_data:
            feed = Feed(
                id=feed_id,
                name=name,
                url=url,
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                group=group,
            )
            upsert_feed(feed)
        return [
            "article-group-feed-1",
            "article-group-feed-2",
            "article-group-feed-3",
            "article-group-feed-4",
        ]

    def _create_articles_for_feeds(self, initialized_db, feed_ids):
        """Helper to create articles for test feeds."""
        from src.storage.sqlite import store_article

        articles = [
            (
                f"{feed_ids[0]}-article-1",
                feed_ids[0],
                "AI in Machine Learning",
                "AI article about ML",
            ),
            (
                f"{feed_ids[0]}-article-2",
                feed_ids[0],
                "Deep Learning Advances",
                "DL article content",
            ),
            (
                f"{feed_ids[1]}-article-1",
                feed_ids[1],
                "LLM like GPT-4",
                "LLM article about GPT",
            ),
            (
                f"{feed_ids[2]}-article-1",
                feed_ids[2],
                "Python Tech News",
                "Tech article about Python",
            ),
            (
                f"{feed_ids[3]}-article-1",
                feed_ids[3],
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

    def test_list_articles_with_groups_filter(self, initialized_db):
        """list_articles() with groups filter returns only articles from those groups."""
        from src.storage.sqlite import list_articles

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # Filter by AI group only
        articles = list_articles(groups=["AI"])
        assert len(articles) == 2  # 2 AI articles
        for article in articles:
            assert article.feed_id == "article-group-feed-1"

    def test_list_articles_with_multiple_groups(self, initialized_db):
        """list_articles() with multiple groups (OR semantics) returns articles from any of those groups."""
        from src.storage.sqlite import list_articles

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # Filter by AI and LLM groups (OR semantics)
        articles = list_articles(groups=["AI", "LLM"])
        feed_ids_returned = {a.feed_id for a in articles}
        assert "article-group-feed-1" in feed_ids_returned  # AI
        assert "article-group-feed-2" in feed_ids_returned  # LLM
        assert "article-group-feed-3" not in feed_ids_returned  # Tech
        assert "article-group-feed-4" not in feed_ids_returned  # Ungrouped

    def test_list_articles_groups_exclude_ungrouped(self, initialized_db):
        """list_articles() with groups filter excludes feeds with NULL group."""
        from src.storage.sqlite import list_articles

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # Filter by AI - should not include ungrouped
        articles = list_articles(groups=["AI"])
        for article in articles:
            assert article.feed_id != "article-group-feed-4"  # Ungrouped feed excluded

    def test_list_articles_with_feed_id_and_groups(self, initialized_db):
        """list_articles() combines feed_id and groups filters (AND logic)."""
        from src.storage.sqlite import list_articles

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # Filter by AI group AND feed-id = article-group-feed-1
        articles = list_articles(feed_id="article-group-feed-1", groups=["AI"])
        assert len(articles) == 2  # Both articles from feed-1
        for article in articles:
            assert article.feed_id == "article-group-feed-1"

    def test_list_articles_no_groups_returns_all(self, initialized_db):
        """list_articles() without groups filter returns all articles."""
        from src.storage.sqlite import list_articles

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # No groups filter - should return all
        articles = list_articles()
        assert len(articles) == 5  # All 5 articles

    def test_search_articles_fts_with_groups(self, initialized_db):
        """search_articles_fts() with groups filter returns only matching articles from those groups."""
        from src.storage.sqlite import search_articles_fts

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # Search for "AI" in AI group only
        articles = search_articles_fts(query="AI", groups=["AI"])
        assert len(articles) >= 1  # At least one AI article
        for article in articles:
            assert article.feed_id == "article-group-feed-1"  # Only AI group

    def test_search_articles_fts_groups_and_feed_id(self, initialized_db):
        """search_articles_fts() combines feed_id and groups filters."""
        from src.storage.sqlite import search_articles_fts

        feed_ids = self._create_feeds_with_groups(initialized_db)
        self._create_articles_for_feeds(initialized_db, feed_ids)

        # Search for "article" in AI group with specific feed
        articles = search_articles_fts(
            query="article", feed_id="article-group-feed-1", groups=["AI"]
        )
        for article in articles:
            assert article.feed_id == "article-group-feed-1"


class TestUpdateArticleContent:
    """Tests for update_article_content function."""

    def test_update_article_content_success(self, initialized_db):
        """update_article_content() updates article content and modified_at."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            get_article_detail,
            store_article,
            update_article_content,
        )

        feed = Feed(
            id="update-content-feed",
            name="Update Content Feed",
            url="https://example.com/update-content.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="update-content-guid",
            title="Original Title",
            content="<p>Original content</p>",
            link="https://example.com/update-content",
            feed_id="update-content-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Verify original content
        detail = get_article_detail(article_id)
        assert detail["content"] == "<p>Original content</p>"

        # Update content
        new_content = "# New Markdown Content\n\nThis is the updated content."
        result = update_article_content(article_id, new_content)

        assert result["success"] is True
        assert result["error"] is None

        # Verify updated content
        updated_detail = get_article_detail(article_id)
        assert updated_detail["content"] == new_content

    def test_update_article_content_with_truncated_id(self, initialized_db):
        """update_article_content() works with truncated 8-char ID."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            get_article_detail,
            store_article,
            update_article_content,
        )

        feed = Feed(
            id="trunc-update-feed",
            name="Trunc Update Feed",
            url="https://example.com/trunc-update.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="trunc-update-guid",
            title="Trunc Update Article",
            content="<p>Original</p>",
            link="https://example.com/trunc-update",
            feed_id="trunc-update-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Use truncated ID
        truncated_id = article_id[:8]
        new_content = "Updated via truncated ID"
        result = update_article_content(truncated_id, new_content)

        assert result["success"] is True

        # Verify full article was updated
        detail = get_article_detail(article_id)
        assert detail["content"] == new_content

    def test_update_article_content_not_found(self, initialized_db):
        """update_article_content() returns error when article not found."""
        from src.storage.sqlite import update_article_content

        result = update_article_content("non-existent-id", "some content")

        assert result["success"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    def test_update_article_content_always_overwrites(self, initialized_db):
        """update_article_content() always overwrites content regardless of previous value."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            get_article_detail,
            store_article,
            update_article_content,
        )

        feed = Feed(
            id="overwrite-feed",
            name="Overwrite Feed",
            url="https://example.com/overwrite.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="overwrite-guid",
            title="Overwrite Article",
            content=None,  # Start with no content
            link="https://example.com/overwrite",
            feed_id="overwrite-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Update with content
        result1 = update_article_content(article_id, "First update")
        assert result1["success"] is True

        # Update again with different content
        result2 = update_article_content(article_id, "Second update")
        assert result2["success"] is True

        # Verify second update overwrote first
        detail = get_article_detail(article_id)
        assert detail["content"] == "Second update"


# =============================================================================
# TestArticleStatus
# =============================================================================


class TestArticleStatus:
    """Tests for mark_article_read, mark_article_unread, toggle_article_star."""

    def _get_article_status(self, article_id: str) -> dict:
        """Read read_at and is_starred directly from DB (get_article_detail omits them)."""
        import sqlite3

        from src.storage.sqlite.conn import get_db_path

        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT read_at, is_starred FROM articles WHERE id = ?",
            (article_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row is None:
            return {}
        return {"read_at": row["read_at"], "is_starred": row["is_starred"]}

    def test_mark_article_read_sets_read_at(self, initialized_db):
        """mark_article_read() sets read_at timestamp on the article."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, mark_article_read, store_article

        feed = Feed(
            id="read-status-feed",
            name="Read Status Feed",
            url="https://example.com/read-status.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="read-status-guid",
            title="Read Status Article",
            content="<p>Content</p>",
            link="https://example.com/read-status",
            feed_id="read-status-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Verify article starts unread
        status = self._get_article_status(article_id)
        assert status["read_at"] is None

        # Mark as read
        result = mark_article_read(article_id)
        assert result["success"] is True
        assert result["error"] is None

        # Verify read_at is now set
        status = self._get_article_status(article_id)
        assert status["read_at"] is not None
        assert len(status["read_at"]) > 0

    def test_mark_article_read_with_truncated_id(self, initialized_db):
        """mark_article_read() works with 8-char truncated article ID."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, mark_article_read, store_article

        feed = Feed(
            id="trunc-read-feed",
            name="Trunc Read Feed",
            url="https://example.com/trunc-read.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="trunc-read-guid",
            title="Trunc Read Article",
            content="<p>Content</p>",
            link="https://example.com/trunc-read",
            feed_id="trunc-read-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Use truncated ID
        result = mark_article_read(article_id[:8])
        assert result["success"] is True

        status = self._get_article_status(article_id)
        assert status["read_at"] is not None

    def test_mark_article_read_not_found(self, initialized_db):
        """mark_article_read() returns error when article does not exist."""
        from src.storage.sqlite import mark_article_read

        result = mark_article_read("non-existent-id")
        assert result["success"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    def test_mark_article_unread_clears_read_at(self, initialized_db):
        """mark_article_unread() clears read_at (sets it back to NULL)."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            mark_article_read,
            mark_article_unread,
            store_article,
        )

        feed = Feed(
            id="unread-status-feed",
            name="Unread Status Feed",
            url="https://example.com/unread-status.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="unread-status-guid",
            title="Unread Status Article",
            content="<p>Content</p>",
            link="https://example.com/unread-status",
            feed_id="unread-status-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Mark as read first
        mark_article_read(article_id)
        assert self._get_article_status(article_id)["read_at"] is not None

        # Mark as unread
        result = mark_article_unread(article_id)
        assert result["success"] is True
        assert result["error"] is None

        # Verify read_at is cleared
        status = self._get_article_status(article_id)
        assert status["read_at"] is None

    def test_mark_article_unread_with_truncated_id(self, initialized_db):
        """mark_article_unread() works with 8-char truncated article ID."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            mark_article_read,
            mark_article_unread,
            store_article,
        )

        feed = Feed(
            id="trunc-unread-feed",
            name="Trunc Unread Feed",
            url="https://example.com/trunc-unread.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="trunc-unread-guid",
            title="Trunc Unread Article",
            content="<p>Content</p>",
            link="https://example.com/trunc-unread",
            feed_id="trunc-unread-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        mark_article_read(article_id)
        result = mark_article_unread(article_id[:8])
        assert result["success"] is True

        status = self._get_article_status(article_id)
        assert status["read_at"] is None

    def test_mark_article_unread_not_found(self, initialized_db):
        """mark_article_unread() returns error when article does not exist."""
        from src.storage.sqlite import mark_article_unread

        result = mark_article_unread("non-existent-id")
        assert result["success"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    def test_toggle_article_star_from_unstarred_to_starred(self, initialized_db):
        """toggle_article_star() stars an unstarred article (NULL -> 1)."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article, toggle_article_star

        feed = Feed(
            id="toggle-star-feed",
            name="Toggle Star Feed",
            url="https://example.com/toggle-star.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="toggle-star-guid",
            title="Toggle Star Article",
            content="<p>Content</p>",
            link="https://example.com/toggle-star",
            feed_id="toggle-star-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Verify article starts unstarred
        status = self._get_article_status(article_id)
        assert status["is_starred"] in (None, 0)

        # Toggle: unstarred -> starred
        result = toggle_article_star(article_id)
        assert result["success"] is True
        assert result["error"] is None
        assert result["is_starred"] is True

        status = self._get_article_status(article_id)
        assert status["is_starred"] == 1

    def test_toggle_article_star_from_starred_to_unstarred(self, initialized_db):
        """toggle_article_star() unstars a starred article (1 -> 0)."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            store_article,
            toggle_article_star,
        )

        feed = Feed(
            id="toggle-unstar-feed",
            name="Toggle Unstar Feed",
            url="https://example.com/toggle-unstar.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="toggle-unstar-guid",
            title="Toggle Unstar Article",
            content="<p>Content</p>",
            link="https://example.com/toggle-unstar",
            feed_id="toggle-unstar-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Star the article first
        toggle_article_star(article_id)
        assert self._get_article_status(article_id)["is_starred"] == 1

        # Toggle: starred -> unstarred
        result = toggle_article_star(article_id)
        assert result["success"] is True
        assert result["is_starred"] is False

        status = self._get_article_status(article_id)
        assert status["is_starred"] == 0

    def test_toggle_article_star_with_truncated_id(self, initialized_db):
        """toggle_article_star() works with 8-char truncated article ID."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article, toggle_article_star

        feed = Feed(
            id="trunc-star-feed",
            name="Trunc Star Feed",
            url="https://example.com/trunc-star.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="trunc-star-guid",
            title="Trunc Star Article",
            content="<p>Content</p>",
            link="https://example.com/trunc-star",
            feed_id="trunc-star-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        result = toggle_article_star(article_id[:8])
        assert result["success"] is True
        assert result["is_starred"] is True

        status = self._get_article_status(article_id)
        assert status["is_starred"] == 1

    def test_toggle_article_star_not_found(self, initialized_db):
        """toggle_article_star() returns error when article does not exist."""
        from src.storage.sqlite import toggle_article_star

        result = toggle_article_star("non-existent-id")
        assert result["success"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower()
        assert result["is_starred"] is None

    def test_mark_article_read_idempotent(self, initialized_db):
        """mark_article_read() is idempotent: calling it twice succeeds both times."""
        from src.models import Feed
        from src.storage.sqlite import (
            add_feed,
            mark_article_read,
            store_article,
        )

        feed = Feed(
            id="idempotent-read-feed",
            name="Idempotent Read Feed",
            url="https://example.com/idempotent-read.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="idempotent-read-guid",
            title="Idempotent Read Article",
            content="<p>Content</p>",
            link="https://example.com/idempotent-read",
            feed_id="idempotent-read-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        result1 = mark_article_read(article_id)
        assert result1["success"] is True

        result2 = mark_article_read(article_id)
        assert result2["success"] is True


# =============================================================================
# TestUpsertArticles
# =============================================================================


class TestUpsertArticles:
    """Tests for upsert_articles batch upsert with mixed new and existing articles."""

    def test_upsert_articles_returns_existing_ids_for_duplicates(self, initialized_db):
        """upsert_articles() ON CONFLICT returns existing article IDs, not new ones."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article, upsert_articles

        feed = Feed(
            id="batch-feed",
            name="Batch Feed",
            url="https://example.com/batch.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        # Pre-store two articles (simulate existing articles)
        existing_id_1 = store_article(
            guid="existing-guid-1",
            title="Existing Article 1",
            content="Existing content 1",
            link="https://example.com/existing1",
            feed_id="batch-feed",
            published_at="2024-01-10T10:00:00+00:00",
        )
        existing_id_2 = store_article(
            guid="existing-guid-2",
            title="Existing Article 2",
            content="Existing content 2",
            link="https://example.com/existing2",
            feed_id="batch-feed",
            published_at="2024-01-11T10:00:00+00:00",
        )

        # Batch upsert with 2 existing + 2 new articles
        articles = [
            {
                "guid": "existing-guid-1",
                "title": "Updated Existing 1",
                "content": "Updated content 1",
                "link": "https://example.com/existing1",
                "feed_id": "batch-feed",
                "published_at": "2024-01-10T10:00:00+00:00",
            },
            {
                "guid": "existing-guid-2",
                "title": "Updated Existing 2",
                "content": "Updated content 2",
                "link": "https://example.com/existing2",
                "feed_id": "batch-feed",
                "published_at": "2024-01-11T10:00:00+00:00",
            },
            {
                "guid": "new-guid-1",
                "title": "New Article 1",
                "content": "New content 1",
                "link": "https://example.com/new1",
                "feed_id": "batch-feed",
                "published_at": "2024-01-20T10:00:00+00:00",
            },
            {
                "guid": "new-guid-2",
                "title": "New Article 2",
                "content": "New content 2",
                "link": "https://example.com/new2",
                "feed_id": "batch-feed",
                "published_at": "2024-01-21T10:00:00+00:00",
            },
        ]

        results = upsert_articles(articles)

        # Must return 4 results in the same order as input
        assert len(results) == 4

        # Existing articles must return the SAME IDs (not new ones)
        result_ids = [r[0] for r in results]
        result_guids = [r[1] for r in results]

        assert result_ids[0] == existing_id_1, (
            "Existing article 1 should return original ID"
        )
        assert result_ids[1] == existing_id_2, (
            "Existing article 2 should return original ID"
        )
        assert result_guids[0] == "existing-guid-1"
        assert result_guids[1] == "existing-guid-2"

        # New articles must return new IDs (different from existing)
        assert result_ids[2] != existing_id_1
        assert result_ids[2] != existing_id_2
        assert result_ids[3] != existing_id_1
        assert result_ids[3] != existing_id_2
        assert (
            result_ids[2] != result_ids[3]
        )  # Two new articles must have different IDs
        assert result_guids[2] == "new-guid-1"
        assert result_guids[3] == "new-guid-2"

    def test_upsert_articles_all_new_returns_distinct_ids(self, initialized_db):
        """upsert_articles() returns distinct IDs when all articles are new."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, upsert_articles

        feed = Feed(
            id="new-batch-feed",
            name="New Batch Feed",
            url="https://example.com/newbatch.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        articles = [
            {
                "guid": "allnew-guid-1",
                "title": "All New 1",
                "content": "Content 1",
                "link": "https://example.com/allnew1",
                "feed_id": "new-batch-feed",
                "published_at": "2024-01-20T10:00:00+00:00",
            },
            {
                "guid": "allnew-guid-2",
                "title": "All New 2",
                "content": "Content 2",
                "link": "https://example.com/allnew2",
                "feed_id": "new-batch-feed",
                "published_at": "2024-01-21T10:00:00+00:00",
            },
            {
                "guid": "allnew-guid-3",
                "title": "All New 3",
                "content": "Content 3",
                "link": "https://example.com/allnew3",
                "feed_id": "new-batch-feed",
                "published_at": "2024-01-22T10:00:00+00:00",
            },
        ]

        results = upsert_articles(articles)

        assert len(results) == 3
        ids = [r[0] for r in results]

        # All IDs must be distinct
        assert len(set(ids)) == 3
        # All IDs must be non-empty strings
        for article_id in ids:
            assert isinstance(article_id, str)
            assert len(article_id) > 0

    def test_upsert_articles_empty_list_returns_empty(self, initialized_db):
        """upsert_articles() with empty list returns empty list."""
        from src.storage.sqlite import upsert_articles

        results = upsert_articles([])
        assert results == []


# =============================================================================
# TestRefreshIntervalCRUD
# =============================================================================


class TestRefreshIntervalCRUD:
    """Tests for refresh_interval CRUD operations in storage layer.

    Covers: add_feed, upsert_feed, get_feed, list_feeds, update_feed_metadata.
    """

    def test_add_feed_stores_refresh_interval(self, initialized_db):
        """add_feed() stores and retrieves feed with refresh_interval."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed

        feed = Feed(
            id="ri-add-feed-1",
            name="Refresh Interval Add Feed",
            url="https://example.com/ri-add.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=7200,
        )
        add_feed(feed)

        stored = get_feed("ri-add-feed-1")
        assert stored is not None
        assert stored.refresh_interval == 7200

    def test_add_feed_with_null_refresh_interval(self, initialized_db):
        """add_feed() handles null refresh_interval (uses global default)."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed

        feed = Feed(
            id="ri-null-feed-1",
            name="Null Refresh Interval Feed",
            url="https://example.com/ri-null.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=None,
        )
        add_feed(feed)

        stored = get_feed("ri-null-feed-1")
        assert stored is not None
        assert stored.refresh_interval is None

    def test_upsert_feed_stores_refresh_interval(self, initialized_db):
        """upsert_feed() stores and retrieves feed with refresh_interval."""
        from src.models import Feed
        from src.storage.sqlite import get_feed, upsert_feed

        feed = Feed(
            id="ri-upsert-feed-1",
            name="Upsert Refresh Interval Feed",
            url="https://example.com/ri-upsert.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=3600,
        )
        result, is_new = upsert_feed(feed)
        assert is_new is True
        assert result.refresh_interval == 3600

        stored = get_feed("ri-upsert-feed-1")
        assert stored is not None
        assert stored.refresh_interval == 3600

    def test_upsert_feed_updates_refresh_interval(self, initialized_db):
        """upsert_feed() updates existing feed's refresh_interval."""
        from src.models import Feed
        from src.storage.sqlite import get_feed, upsert_feed

        feed1 = Feed(
            id="ri-update-ri-1",
            name="Update Refresh Interval Feed",
            url="https://example.com/ri-update.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=1800,
        )
        upsert_feed(feed1)

        # Update with new refresh_interval
        feed2 = Feed(
            id="ri-update-ri-1",
            name="Update Refresh Interval Feed",
            url="https://example.com/ri-update.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=10800,
        )
        result, is_new = upsert_feed(feed2)
        assert is_new is False
        assert result.refresh_interval == 10800

        stored = get_feed("ri-update-ri-1")
        assert stored is not None
        assert stored.refresh_interval == 10800

    def test_get_feed_returns_refresh_interval(self, initialized_db):
        """get_feed() returns feed with refresh_interval value."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed

        feed = Feed(
            id="ri-get-feed-1",
            name="Get Refresh Interval Feed",
            url="https://example.com/ri-get.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=5400,
        )
        add_feed(feed)

        result = get_feed("ri-get-feed-1")
        assert result is not None
        assert result.id == "ri-get-feed-1"
        assert result.refresh_interval == 5400

    def test_get_feed_nonexistent_returns_none(self, initialized_db):
        """get_feed() with non-existing ID returns None."""
        from src.storage.sqlite import get_feed

        result = get_feed("non-existent-ri-feed")
        assert result is None

    def test_list_feeds_returns_refresh_intervals(self, initialized_db):
        """list_feeds() returns feeds with their refresh_interval values."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, list_feeds

        feeds = [
            Feed(
                id="ri-list-feed-1",
                name="List Refresh Interval Feed 1",
                url="https://example.com/ri-list1.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                refresh_interval=600,
            ),
            Feed(
                id="ri-list-feed-2",
                name="List Refresh Interval Feed 2",
                url="https://example.com/ri-list2.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-02T00:00:00+00:00",
                refresh_interval=3600,
            ),
            Feed(
                id="ri-list-feed-3",
                name="List Refresh Interval Feed 3",
                url="https://example.com/ri-list3.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-03T00:00:00+00:00",
                refresh_interval=None,
            ),
        ]
        for feed in feeds:
            add_feed(feed)

        result = list_feeds()
        assert len(result) == 3

        # Verify refresh_intervals are returned correctly
        for feed in result:
            if feed.id == "ri-list-feed-1":
                assert feed.refresh_interval == 600
            elif feed.id == "ri-list-feed-2":
                assert feed.refresh_interval == 3600
            elif feed.id == "ri-list-feed-3":
                assert feed.refresh_interval is None

    def test_update_feed_metadata_refresh_interval_success(self, initialized_db):
        """update_feed_metadata() successfully updates refresh_interval."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed, update_feed_metadata

        feed = Feed(
            id="ri-update-meta-1",
            name="Update Meta Refresh Interval Feed",
            url="https://example.com/ri-update-meta.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=None,
        )
        add_feed(feed)

        # Update refresh_interval
        result, success = update_feed_metadata(
            "ri-update-meta-1", refresh_interval=1800
        )
        assert success is True
        assert result is not None
        assert result.refresh_interval == 1800

        # Verify persisted
        stored = get_feed("ri-update-meta-1")
        assert stored.refresh_interval == 1800

    def test_update_feed_metadata_refresh_interval_none_does_not_update(
        self, initialized_db
    ):
        """update_feed_metadata() with refresh_interval=None does not update (no-op)."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed, update_feed_metadata

        feed = Feed(
            id="ri-update-none-1",
            name="Update To None Feed",
            url="https://example.com/ri-update-none.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=3600,
        )
        add_feed(feed)

        # Pass refresh_interval=None - should be no-op (keeps current value)
        result, success = update_feed_metadata(
            "ri-update-none-1", refresh_interval=None
        )
        assert success is False
        assert result is not None
        # refresh_interval should remain unchanged
        assert result.refresh_interval == 3600

        # Verify persisted
        stored = get_feed("ri-update-none-1")
        assert stored.refresh_interval == 3600

    def test_update_feed_metadata_multiple_fields_including_refresh_interval(
        self,
        initialized_db,
    ):
        """update_feed_metadata() can update refresh_interval along with other fields."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, get_feed, update_feed_metadata

        feed = Feed(
            id="ri-multi-meta-1",
            name="Multi Meta Feed",
            url="https://example.com/ri-multi.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            weight=0.3,
            group=None,
            refresh_interval=1800,
        )
        add_feed(feed)

        # Update multiple fields including refresh_interval
        result, success = update_feed_metadata(
            "ri-multi-meta-1",
            weight=0.7,
            group="Tech",
            refresh_interval=7200,
        )
        assert success is True
        assert result is not None
        assert result.weight == 0.7
        assert result.group == "Tech"
        assert result.refresh_interval == 7200

        # Verify persisted
        stored = get_feed("ri-multi-meta-1")
        assert stored.weight == 0.7
        assert stored.group == "Tech"
        assert stored.refresh_interval == 7200

    def test_update_feed_metadata_refresh_interval_not_found(self, initialized_db):
        """update_feed_metadata() with non-existing feed_id returns (None, False)."""
        from src.storage.sqlite import update_feed_metadata

        result, success = update_feed_metadata(
            "non-existent-ri-feed", refresh_interval=3600
        )
        assert success is False
        assert result is None

    def test_update_feed_metadata_no_fields_returns_current(self, initialized_db):
        """update_feed_metadata() with no fields to update returns current feed without changes."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, update_feed_metadata

        feed = Feed(
            id="ri-nochange-1",
            name="No Change Feed",
            url="https://example.com/ri-nochange.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
            refresh_interval=3600,
        )
        add_feed(feed)

        # Update with no fields
        result, success = update_feed_metadata("ri-nochange-1")
        assert success is False
        assert result is not None
        assert result.refresh_interval == 3600
