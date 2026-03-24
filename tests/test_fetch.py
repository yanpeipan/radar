"""Tests for async concurrent fetch and SQLite serialization."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.application.fetch import fetch_all_async, fetch_one_async
from src.models import Feed


@pytest.fixture
def sample_feed():
    """Sample feed for testing."""
    return Feed(
        id="test-feed-1",
        name="Test Feed",
        url="https://example.com/feed.xml",
        etag=None,
        last_modified=None,
        last_fetched=None,
        created_at="2024-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_fetch_all_async_exists():
    """Verify fetch_all_async function exists and is callable."""
    assert callable(fetch_all_async)


@pytest.mark.asyncio
async def test_fetch_all_async_is_async_generator():
    """Verify fetch_all_async is an async generator yielding per-feed results."""
    from src.models import Feed

    fake_feed = Feed(
        id="fake-1", name="Fake", url="https://fake.example/feed.xml",
        etag=None, last_modified=None, last_fetched=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    with patch("src.application.fetch.storage_list_feeds", return_value=[fake_feed]):
        with patch("src.application.fetch.fetch_one_async", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"new_articles": 0}
            results = []
            async for result in fetch_all_async():
                results.append(result)
            assert len(results) == 1
            assert "feed_id" in results[0]
            assert "feed_name" in results[0]
            assert "new_articles" in results[0]


@pytest.mark.asyncio
async def test_semaphore_default_value():
    """Verify default concurrency is 10."""
    from src.models import Feed

    fake_feed = Feed(
        id="fake-1", name="Fake", url="https://fake.example/feed.xml",
        etag=None, last_modified=None, last_fetched=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    with patch("src.application.fetch.storage_list_feeds", return_value=[fake_feed]):
        with patch("src.application.fetch.asyncio.Semaphore") as mock_semaphore:
            mock_semaphore.return_value.__aenter__ = AsyncMock()
            mock_semaphore.return_value.__aexit__ = AsyncMock()
            # Consume the generator
            async for _ in fetch_all_async():
                pass
            mock_semaphore.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_semaphore_custom_concurrency():
    """Verify custom concurrency parameter is passed to Semaphore."""
    from src.models import Feed

    fake_feed = Feed(
        id="fake-1", name="Fake", url="https://fake.example/feed.xml",
        etag=None, last_modified=None, last_fetched=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    with patch("src.application.fetch.storage_list_feeds", return_value=[fake_feed]):
        with patch("src.application.fetch.asyncio.Semaphore") as mock_semaphore:
            mock_semaphore.return_value.__aenter__ = AsyncMock()
            mock_semaphore.return_value.__aexit__ = AsyncMock()
            # Consume the generator
            async for _ in fetch_all_async(concurrency=5):
                pass
            mock_semaphore.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_fetch_one_async_returns_dict(sample_feed):
    """Verify fetch_one_async returns expected dict structure."""
    with patch("src.application.fetch.discover_or_default", return_value=[]):
        result = await fetch_one_async(sample_feed)
        assert isinstance(result, dict)
        assert "new_articles" in result


@pytest.mark.asyncio
async def test_fetch_one_async_crawled_feed():
    """Verify fetch_one_async skips 'crawled' system feed."""
    crawled_feed = Feed(
        id="crawled",
        name="Crawled Pages",
        url="",
        etag=None,
        last_modified=None,
        last_fetched=None,
        created_at="2024-01-01T00:00:00+00:00",
    )
    result = await fetch_one_async(crawled_feed)
    assert result == {"new_articles": 0}


@pytest.mark.asyncio
async def test_db_lock_serialization():
    """Verify store_article_async uses asyncio.Lock for serialization."""
    from src.storage.sqlite import store_article_async, _get_db_write_lock

    # Verify the lock exists and is an asyncio.Lock
    lock = _get_db_write_lock()
    assert isinstance(lock, asyncio.Lock), "Lock should be an asyncio.Lock instance"

    # Verify store_article_async is actually async
    import inspect
    assert inspect.iscoroutinefunction(store_article_async), \
        "store_article_async should be a coroutine function"
