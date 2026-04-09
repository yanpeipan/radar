# Testing Patterns

**Analysis Date:** 2026-03-31

## Test Framework

**Runner:** pytest 9.0.2+
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` - auto-detect async tests
- `testpaths = ["tests"]`

**Assertion Library:** pytest built-in assertions

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest --tb=short               # Short tracebacks
pytest --strict-markers         # Fail on unknown markers
pytest -k "test_name"          # Run tests matching pattern
pytest --cov=src                # With coverage
pytest -x                       # Stop on first failure
```

## Test File Organization

**Location:** `tests/` directory (parallel to `src/`)

**Naming:** `test_<module>.py` pattern (e.g., `test_config.py`, `test_fetch.py`)

**Structure:**
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_cli.py             # CLI integration tests
├── test_config.py          # Config tests
├── test_fetch.py           # Fetch module tests
├── test_providers.py       # Provider tests
└── test_storage.py         # Storage layer tests
```

## Test Fixtures (conftest.py)

**Database Fixtures:**

```python
@pytest.fixture(scope="function")
def temp_db_path(tmp_path):
    """Create a temporary database file path for each test (isolated per test)."""
    db_path = tmp_path / "test.db"
    yield str(db_path)

@pytest.fixture(scope="function")
def initialized_db(temp_db_path, monkeypatch):
    """Database that has been initialized with schema (tables created).

    Patches impl module _DB_PATH to use temp_db_path before initialization.
    """
    from src.storage.sqlite import impl
    monkeypatch.setattr(impl, "_DB_PATH", Path(temp_db_path))
    impl.init_db()
    yield temp_db_path
```

**Sample Data Fixtures:**

```python
@pytest.fixture
def sample_feed():
    """Sample feed for testing. Returns a Feed dataclass instance."""
    from src.models import Feed
    return Feed(
        id="test-feed-1",
        name="Test Feed",
        url="https://example.com/feed.xml",
        ...
    )

@pytest.fixture
def sample_article():
    """Sample article data for testing. Returns a dict."""
    return {
        "id": "test-article-1",
        "title": "Test Article Title",
        ...
    }
```

**CLI Fixtures:**

```python
@pytest.fixture
def cli_runner():
    """Click CliRunner for testing CLI commands."""
    return CliRunner()
```

## Test Structure

**Class-based organization:**
```python
class TestArticleOperations:
    """Tests for article storage functions..."""

    def test_store_article_returns_nanoid_format(self, initialized_db):
        """store_article() stores article and returns article_id in nanoid format."""
        from src.storage.sqlite import add_feed, store_article
        ...
```

**Individual function tests:**
```python
def test_get_timezone_returns_zoneinfo():
    """get_timezone should return a ZoneInfo object."""
    from src.application.config import get_timezone
    result = get_timezone()
    assert isinstance(result, ZoneInfo)
```

## Mocking

**Framework:** pytest-mock + unittest.mock

**Async mocking with AsyncMock:**
```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_fetch_all_async_is_async_generator():
    fake_feed = Feed(...)
    with (
        patch("src.application.fetch.storage_list_feeds", return_value=[fake_feed]),
        patch("src.application.fetch.fetch_one_async", new_callable=AsyncMock) as mock_fetch,
    ):
        mock_fetch.return_value = {"new_articles": 0}
        async for result in fetch_all_async():
            ...
```

**MagicMock for objects with attributes:**
```python
mock_response = MagicMock()
mock_response.status = 200
mock_response.headers = {"content-type": "application/rss+xml"}
mock_response.body = rss_xml
```

**Patch patterns:**
```python
with patch("module.function", return_value=value):
    ...

with patch("module.function", new_callable=AsyncMock) as mock_func:
    mock_func.return_value = expected_value
    ...
```

## What to Mock vs Real

**DO Mock:**
- HTTP responses (use `MagicMock` or `httpx_mock`)
- External services (GitHub API, etc.)
- `asyncio.Semaphore` (to verify calls)
- Module-level functions that return deterministic test data

**DO NOT Mock:**
- SQLite operations - use `initialized_db` fixture with real database
- Storage layer functions - test with real DB via `initialized_db`
- Private functions (prefixed with `_`) - test public interfaces only

## Test Conventions (documented in conftest.py)

```
1. NO PRIVATE FUNCTION TESTING
   - Do NOT test functions prefixed with underscore (_private_func)
   - Do NOT test implementation details
   - Test ONLY public interfaces: module-level functions, class public methods

2. REAL DATABASE VIA tmp_path
   - Use the temp_db_path or initialized_db fixture for ALL database tests
   - Do NOT mock sqlite3 or storage functions
   - Real SQLite operations ensure integration works correctly

3. HTTP MOCKING WITH httpx_mock
   - Use pytest-httpx's httpx_mock fixture for HTTP requests
   - Do NOT make real network calls in tests
   - Register mock responses before calling code that makes HTTP requests

4. CLI TESTING WITH CliRunner
   - Use click.testing.CliRunner for all CLI tests
   - Use isolated_filesystem() for commands that write files
   - Pass db path explicitly via CLI arguments or monkeypatch
```

## Async Testing

**Mark async tests:**
```python
@pytest.mark.asyncio
async def test_fetch_all_async_exists():
    assert callable(fetch_all_async)
```

**Async generator testing:**
```python
@pytest.mark.asyncio
async def test_fetch_all_async_is_async_generator():
    ...
    results = []
    async for result in fetch_all_async():
        results.append(result)
    assert len(results) == 1
```

**Verify async behavior:**
```python
@pytest.mark.asyncio
async def test_db_lock_serialization():
    from src.storage.sqlite import _get_db_write_lock, store_article_async
    import inspect

    lock = _get_db_write_lock()
    assert isinstance(lock, asyncio.Lock)
    assert inspect.iscoroutinefunction(store_article_async)
```

## Fixtures and Factories

**Factory pattern for test data:**
```python
# Create Feed manually in tests
feed = Feed(
    id="feed-1",
    name="Test Feed",
    url="https://example.com/feed.xml",
    etag=None,
    modified_at=None,
    fetched_at=None,
    created_at="2024-01-01T00:00:00+00:00",
)
```

**Test isolation:**
- Each test gets fresh database via `initialized_db` fixture
- No shared state between tests
- `scope="function"` ensures isolation

## Test Coverage

**Target:** Not explicitly enforced in current config

**View Coverage:**
```bash
pytest --cov=src --cov-report=term-missing
```

**Key coverage areas:**
- Storage layer (SQLite operations)
- Provider matching and fetching
- CLI commands
- Async fetch orchestration

## Common Patterns

**Async testing with semaphore verification:**
```python
@pytest.mark.asyncio
async def test_semaphore_default_value():
    from src.models import Feed
    fake_feed = Feed(...)
    with (
        patch("src.application.fetch.storage_list_feeds", return_value=[fake_feed]),
        patch("src.application.fetch.asyncio.Semaphore") as mock_semaphore,
    ):
        mock_semaphore.return_value.__aenter__ = AsyncMock()
        mock_semaphore.return_value.__aexit__ = AsyncMock()
        async for _ in fetch_all_async():
            pass
        mock_semaphore.assert_called_once_with(10)
```

**CLI integration testing:**
```python
def test_feed_add_success(self, cli_runner, initialized_db, monkeypatch):
    from src.discovery.models import DiscoveredFeed, DiscoveredResult

    mock_result = DiscoveredResult(...)
    async def mock_discover_feeds(url, depth, auto_discover):
        return mock_result

    monkeypatch.setattr("src.cli.feed.discover_feeds", mock_discover_feeds)

    result = cli_runner.invoke(cli, ["feed", "add", "--no-auto-discover", "https://example.com/feed.xml"], input="a\n")
    assert result.exit_code == 0
    assert "Added" in result.output
```

**Database operations testing:**
```python
def test_store_article_returns_nanoid_format(self, initialized_db):
    from src.models import Feed
    from src.storage.sqlite import add_feed, store_article

    feed = Feed(...)
    add_feed(feed)

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
    assert article_id.replace("-", "").replace("_", "").isalnum()
```

---

*Testing analysis: 2026-03-31*
