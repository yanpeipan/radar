"""Pytest fixtures for radar tests."""

import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

# --- Database Fixtures ---


@pytest.fixture(scope="function")
def temp_db_path(tmp_path):
    """Create a temporary database file path for each test (isolated per test).

    Convention: Tests must NOT share database state. Each test gets its own
    temporary database via pytest's tmp_path fixture.
    """
    db_path = tmp_path / "test.db"
    yield str(db_path)
    # Cleanup of tmp_path handled automatically by pytest


@pytest.fixture(scope="function")
def initialized_db(temp_db_path, monkeypatch):
    """Database that has been initialized with schema (tables created).

    Patches conn module _DB_PATH to use temp_db_path before initialization.
    After the domain split (conn.py / feeds.py / articles.py / llm.py /
    search.py), _DB_PATH lives in conn.py — patch it there so that get_db()
    and init_db() both use the temp path.
    """
    from src.storage.sqlite import conn

    # Close any existing cached connection BEFORE patching _DB_PATH.
    # Without this, subsequent tests would reuse the old connection.
    conn._close_connection()

    # Patch _DB_PATH in conn module (where it's actually defined)
    monkeypatch.setattr(conn, "_DB_PATH", Path(temp_db_path))

    # Initialize the schema
    conn.init_db()

    yield temp_db_path

    # Cleanup happens automatically via tmp_path


# --- Sample Data Fixtures ---


@pytest.fixture
def sample_feed():
    """Sample feed for testing.

    Returns a Feed dataclass instance with test data.
    """
    from src.models import Feed

    return Feed(
        id="test-feed-1",
        name="Test Feed",
        url="https://example.com/feed.xml",
        etag=None,
        modified_at=None,
        fetched_at=None,
        created_at="2024-01-01T00:00:00+00:00",
    )


@pytest.fixture
def sample_article():
    """Sample article data for testing.

    Returns a dict with article data, compatible with store_article().
    """
    return {
        "id": "test-article-1",
        "title": "Test Article Title",
        "url": "https://example.com/article",
        "description": "This is a test article description",
        "content": "<p>Full article content here</p>",
        "source": "test",
        "published_at": "2024-01-15T10:30:00+08:00",
    }


# --- CLI Fixtures ---


@pytest.fixture
def cli_runner():
    """Click CliRunner for testing CLI commands.

    Use isolated_filesystem() for commands that create files.
    """
    return CliRunner()


# --- Test Conventions (documented for reference) ---

"""
TEST CONVENTIONS FOR THIS PROJECT:

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
"""
