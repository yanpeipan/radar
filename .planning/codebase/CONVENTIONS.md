# Coding Conventions

**Analysis Date:** 2026-03-31

## Languages

**Primary:**
- Python 3.10+ (CLI tool, async operations, data processing)
- Target version: py310 (configured in `pyproject.toml`)

## Formatting & Linting

**Formatter:** ruff-format
- Quote style: double
- Indent style: space
- Docstring code format: enabled
- Line length: 88 characters

**Linter:** ruff
- Selected rules: E, W, F, I, UP, B, C4, SIM
- Ignored: E501 (line too long - handled by formatter)
- Per-file ignores:
  - `__init__.py`: F401, E402
  - `src/cli/*.py`: E402
  - `tests/**/*.py`: E402, F401

**Pre-commit hooks:**
- `trailing-whitespace` - remove trailing whitespace
- `end-of-file-fixer` - ensure files end with newline
- `check-yaml` - validate YAML files
- `check-added-large-files` - prevent large files
- `detect-private-key` - detect SSH private keys
- `ruff` with --fix - auto-fix issues
- `ruff-format` - auto-format

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `async_utils.py`, `fetch.py`)
- Test files: `test_<module>.py` or `<module>_test.py`
- Private modules: prefix with underscore `_utils.py`

**Functions:**
- Public functions: `snake_case` (e.g., `fetch_all_async`, `store_article`)
- Private functions: `_leading_underscore` (e.g., `_get_db_write_lock`, `_normalize_published_at`)
- Async functions: `snake_case` with `_async` suffix (e.g., `fetch_one_async`, `store_article_async`)
- Methods on providers: `snake_case` (e.g., `fetch_articles`, `parse_feed`)

**Variables:**
- snake_case: `temp_db_path`, `article_id`, `concurrency`
- Private: `_leading_underscore` for module-level singletons

**Types/Classes:**
- PascalCase: `Feed`, `Article`, `ContentProvider`, `FetchedResult`
- Dataclass decorator: used for data containers
- Enum: PascalCase members (e.g., `FeedType.RSS`)

**Constants:**
- SCREAMING_SNAKE_CASE for module-level constants: `_DB_PATH`, `_DB_WRITE_LOCK`

## Code Style

**Imports organization:**
1. `from __future__ import annotations` (if present)
2. Standard library
3. Third-party packages
4. Local imports (`from src...`)

**Type hints:**
- Used throughout with `from __future__ import annotations` for forward references
- Union syntax: `str | None` (not `Optional[str]`)
- Return type annotations on all public functions

**Docstrings:**
- Module-level docstrings for all modules (Google-style)
- Class docstrings with Attributes section
- Function docstrings with Args/Returns sections
- Example in `src/models.py`:
  ```python
  @dataclass
  class Feed:
      """Represents an RSS or Atom feed source.

      Attributes:
          id: Unique identifier for the feed.
          name: Display name of the feed.
          url: URL of the feed.
          ...
      """
  ```

**Annotations for None:**
- Use `X | None` syntax (e.g., `str | None`, `list[str] | None`)
- Not `Optional[X]`

## Import Organization

**Pattern in source files:**
```python
from __future__ import annotations

import asyncio
import logging
import time

from src.application.feed import FeedNotFoundError, fetch_one, get_feed
from src.models import Feed, FeedType
from src.providers import match_first
from src.storage import list_feeds as storage_list_feeds
from src.storage import update_feed as storage_update_feed
```

**Path aliases:**
- Local imports use `from src.<module>` pattern
- No path alias configuration (direct module paths)

## Error Handling

**Patterns:**
1. **Return error dict** - Functions return `{"new_articles": 0, "error": "message"}` for recoverable errors
2. **Raise exceptions** - For unrecoverable errors (e.g., `FeedNotFoundError`)
3. **Log and continue** - Non-critical failures logged with `logger.warning()` (e.g., embedding failures)

**Example from `src/application/fetch.py`:**
```python
try:
    result = await asyncio.to_thread(provider.fetch_articles, feed)
except Exception as e:
    logger.error("Failed to fetch_articles %s: %s", feed.url, e)
    return {"new_articles": 0, "error": str(e)}
```

**CLI error handling:**
```python
try:
    result = uvloop.run(fetch_one_async_by_id(feed_id))
except Exception as e:
    click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")
    logger.exception("Failed to fetch feeds")
    sys.exit(1)
```

## Logging

**Framework:** Python standard `logging` module

**Pattern:**
```python
logger = logging.getLogger(__name__)
```

**Levels:**
- `logger.debug()` - verbose diagnostic
- `logger.info()` - significant events
- `logger.warning()` - non-critical failures (continues operation)
- `logger.error()` - significant failures
- `logger.exception()` - errors with traceback

**Log format:** Uses default Python logging format (configured elsewhere)

## Function Design

**Size:** Functions tend to be focused (30-150 lines typical)

**Parameters:**
- Type hints on all parameters
- Default values when sensible
- Use `*args, **kwargs` sparingly

**Return Values:**
- Always return meaningful values (not None for success cases)
- Use dict returns for operations with multiple outcomes
- Document all return values in docstring

## Module Design

**Exports:** Module-level functions, not classes where functions suffice

**Dataclasses over dictionaries for structured data:**
```python
@dataclass
class Feed:
    id: str
    name: str
    url: str
    ...
```

**Protocol for plugin architecture:**
```python
@runtime_checkable
class ContentProvider(Protocol):
    def match(self, url: str, response: Response = None, feed_type: FeedType = None) -> bool: ...
    def priority(self) -> int: ...
    def fetch_articles(self, feed: Feed) -> FetchedResult: ...
```

## Async Patterns

**uvloop for event loop:**
```python
import uvloop
uvloop.run(async_function())
```

**Async semaphore for concurrency limiting:**
```python
semaphore = asyncio.Semaphore(concurrency)
async with semaphore:
    result = await process_feed(feed)
```

**Async serialization for SQLite writes:**
```python
async with lock:
    return await asyncio.to_thread(sync_function, args)
```

**Async generators for streaming results:**
```python
async def fetch_all_async(concurrency: int = 10):
    ...
    for coro in asyncio.as_completed(tasks):
        result = await coro
        yield result
```

## Database Patterns

**Connection management:**
```python
from contextlib import contextmanager

@contextmanager
def get_db():
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()

# Usage
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute(...)
    conn.commit()
```

**Singleton pattern for asyncio lock:**
```python
_db_write_lock: asyncio.Lock | None = None

def _get_db_write_lock() -> asyncio.Lock:
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock
```

---

*Convention analysis: 2026-03-31*
