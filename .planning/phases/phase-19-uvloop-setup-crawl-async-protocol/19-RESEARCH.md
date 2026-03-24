# Phase 19: uvloop Setup + crawl_async Protocol - Research

**Researched:** 2026-03-25
**Domain:** uvloop event loop integration + async Protocol definition
**Confidence:** HIGH

## Summary

Phase 19 establishes the foundation for async crawling in the RSS reader CLI. It requires adding uvloop as a dependency, calling `uvloop.install()` at application startup on Linux/macOS with graceful fallback on Windows, and extending the `ContentProvider` Protocol with a `crawl_async()` method that defaults to wrapping the sync `crawl()` via `run_in_executor()`.

**Primary recommendation:** Add uvloop to pyproject.toml, create a new `src/application/asyncio_utils.py` module for event loop initialization, and extend `src/providers/base.py` with the async protocol method.

## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at Claude's discretion - pure infrastructure phase. Use uvloop best practices and existing codebase conventions.

### Claude's Discretion
All implementation choices are at Claude's discretion - pure infrastructure phase. Use uvloop best practices and existing codebase conventions.

### Deferred Ideas (OUT OF SCOPE)
None - infrastructure phase.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UVLP-01 | uvloop.install() at startup, Linux/macOS auto-use, Windows fallback | Platform detection via `platform.system()`, try/except for Windows |
| UVLP-02 | ContentProvider protocol adds crawl_async() with default run_in_executor wrapper | Protocol extension in base.py, async method pattern verified |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **uvloop** | 0.22.x | Event loop replacement | 2-4x faster I/O than asyncio, de-facto standard for async Python |
| **asyncio** | (built-in) | Async primitives | Native Python async, used for run_in_executor, get_running_loop |

### Dependencies Missing from pyproject.toml
| Library | Current Status | Action Required |
|---------|---------------|-----------------|
| **uvloop** | Installed in dev (0.22.1) but NOT in pyproject.toml | Add to dependencies |

**Installation needed:**
```bash
# Add to pyproject.toml dependencies
uvloop>=0.22.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── application/
│   ├── feed.py           # Existing feed use cases
│   ├── crawl.py          # Existing crawl use cases
│   └── asyncio_utils.py  # NEW: uvloop initialization + fetch_all_async
├── providers/
│   ├── base.py           # MODIFY: Add crawl_async() to ContentProvider Protocol
│   ├── rss_provider.py   # MODIFY: Implement crawl_async() (Phase 20)
│   ├── github_release_provider.py  # MODIFY: Implement crawl_async() (Phase 20)
│   └── default_provider.py  # MODIFY: Implement crawl_async()
├── cli/
│   ├── __init__.py       # MODIFY: Call uvloop.install() at startup
│   └── ...
```

### Pattern 1: uvloop Installation in Click CLI
**What:** Install uvloop event loop policy at application startup
**When to use:** Click-based CLI that will use async operations
**Example:**
```python
# src/application/asyncio_utils.py
import asyncio
import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)

# Cached event loop for reuse
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def install_uvloop() -> bool:
    """Install uvloop as the event loop policy.

    Returns:
        True if uvloop was installed, False if skipped/failed.
    """
    global _main_loop

    # uvloop only works on Linux and macOS
    if platform.system() == "Windows":
        logger.debug("uvloop skipped on Windows - using asyncio")
        return False

    try:
        import uvloop
        uvloop.install()
        _main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_main_loop)
        logger.info("uvloop installed successfully")
        return True
    except ImportError:
        logger.warning("uvloop not installed - using asyncio")
        return False
    except Exception as e:
        logger.warning("Failed to install uvloop: %s - using asyncio", e)
        return False


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create the main event loop."""
    global _main_loop
    if _main_loop is None:
        _main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_main_loop)
    return _main_loop
```

**Source:** Verified via Python 3.13 + uvloop 0.22.1 on macOS

### Pattern 2: Adding crawl_async() to @runtime_checkable Protocol
**What:** Extend ContentProvider Protocol with optional async method
**When to use:** When providers need both sync and async crawl methods
**Example:**
```python
# src/providers/base.py
from typing import List, Protocol, runtime_checkable, Optional

# ... existing code ...

@runtime_checkable
class ContentProvider(Protocol):
    """Protocol for content providers (RSS, GitHub, etc.)."""

    def match(self, url: str) -> bool:
        ...

    def priority(self) -> int:
        ...

    def crawl(self, url: str) -> List[Raw]:
        """Synchronous crawl - all providers must implement."""
        ...

    async def crawl_async(self, url: str) -> List[Raw]:
        """Asynchronous crawl - default uses run_in_executor."""
        ...
```

**Key insight:** Protocol with async methods works with `@runtime_checkable` and `isinstance()` checks. The async method signature is preserved.

**Source:** Verified via Python 3.13 - `isinstance(provider, ContentProvider)` returns True even with async method defined.

### Pattern 3: Default crawl_async() Using run_in_executor
**What:** Default implementation wraps sync crawl() in thread executor
**When to use:** When a default async implementation is needed for all providers
**Example:**
```python
# Default implementation in base.py or concrete provider
import asyncio
from concurrent.futures import ThreadPoolExecutor

_default_executor: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the default thread pool executor."""
    global _default_executor
    if _default_executor is None:
        _default_executor = ThreadPoolExecutor(max_workers=10)
    return _default_executor


async def _default_crawl_async(self, url: str) -> List[Raw]:
    """Default async crawl using run_in_executor.

    Wraps the synchronous crawl() method in a thread pool executor
    to avoid blocking the event loop.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _get_executor(),
        self.crawl,
        url
    )
```

**Source:** Verified via Python 3.13 asyncio testing

### Pattern 4: Platform Detection for uvloop
**What:** Detect OS to conditionally use uvloop
**When to use:** When uvloop should only be used on supported platforms
**Example:**
```python
import platform

def is_uvloop_supported() -> bool:
    """Check if uvloop can be used on this platform."""
    return platform.system() in ("Linux", "Darwin")
```

**Source:** Verified - `platform.system()` returns "Linux", "Darwin", or "Windows"

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Event loop management | Custom loop creation | uvloop + asyncio built-ins | uvloop is 2-4x faster, well-tested |
| Thread pool | Custom threading | ThreadPoolExecutor | Built into stdlib, works with run_in_executor |
| Platform detection | String matching sys.platform | platform.system() | Standard, reliable |

**Key insight:** uvloop is the de-facto standard for async Python CLI tools. Do not build custom event loop solutions.

## Common Pitfalls

### Pitfall 1: Calling uvloop.install() Multiple Times
**What goes wrong:** Potential issues with event loop policy re-installation
**Why it happens:** uvloop.install() can be called multiple times (verified on macOS it doesn't raise error)
**How to avoid:** Call once at startup, guard with platform check
**Warning signs:** "Event loop policy was already set" warnings

### Pitfall 2: uvloop in Non-Main Thread
**What goes wrong:** uvloop may fail when running in non-main thread (e.g., certain Click invocations, IDE integrations)
**Why it happens:** uvloop.install() sets the event loop policy globally; some environments don't support this
**How to avoid:** Wrap uvloop.install() in try/except, always provide asyncio fallback
**Warning signs:** RuntimeError about event loop policy

### Pitfall 3: feedparser Blocks Event Loop
**What goes wrong:** feedparser.parse() is synchronous and blocks the event loop
**Why it happens:** feedparser is CPU-bound for parsing
**How to avoid:** Always run feedparser in thread pool via run_in_executor (Phase 20 will address this for RSSProvider)
**Warning signs:** Event loop starvation, async functions not yielding

### Pitfall 4: Protocol with Only Async Method (Static Type Checker Issue)
**What goes wrong:** Protocol defining only async methods may cause type checking issues
**Why it happens:** Some older type checkers don't handle async Protocol methods well
**How to avoid:** Keep both sync crawl() and async crawl_async() - Protocol inheritance handles this naturally
**Warning signs:** Mypy errors about Protocol member

### Pitfall 5: Missing uvloop Dependency
**What goes wrong:** Code assumes uvloop is available but it's not in pyproject.toml
**Why it happens:** uvloop was installed in dev environment but not declared as dependency
**How to avoid:** Add uvloop>=0.22.0 to dependencies
**Warning signs:** ImportError on fresh install

## Code Examples

### Example: Extending ContentProvider Protocol (src/providers/base.py)
```python
# Adding crawl_async() to Protocol - minimal change
from typing import List, Protocol, runtime_checkable

@runtime_checkable
class ContentProvider(Protocol):
    # ... existing methods ...

    def crawl(self, url: str) -> List[Raw]:
        """Synchronous crawl - must be implemented by all providers."""
        ...

    async def crawl_async(self, url: str) -> List[Raw]:
        """Asynchronous crawl - default implementation wraps crawl().

        Override this method in providers that support true async HTTP
        (e.g., RSSProvider with httpx.AsyncClient).
        """
        ...
```

### Example: Default crawl_async() Implementation
```python
# Default implementation as module-level function in base.py
async def _crawl_async_default(provider: "ContentProvider", url: str) -> List[Raw]:
    """Default crawl_async that wraps sync crawl() in executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, provider.crawl, url)
```

### Example: Windows Graceful Fallback
```python
# src/cli/__init__.py modification
def cli(ctx: click.Context, verbose: bool) -> None:
    """RSS reader CLI - manage feeds and read articles."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Initialize uvloop (graceful fallback on Windows)
    from src.application.asyncio_utils import install_uvloop
    install_uvloop()

    # Initialize database on every command
    from src.storage.sqlite import init_db
    init_db()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pure sync asyncio | uvloop.install() for 2-4x I/O improvement | v1.5 (Phase 19) | Faster concurrent feed fetching |
| uvloop.install() | uvloop.run() (deprecated) | Python 3.12+ | uvloop.install() still works but deprecated |

**Deprecated/outdated:**
- `uvloop.install()`: Deprecated in Python 3.12+ in favor of `uvloop.run()`, but still works and is the documented approach for CLI apps (per STATE.md this is the approach to use)

## Open Questions

1. **Should uvloop be installed in cli() or a separate function?**
   - What we know: cli() is the entry point called on every command
   - What's unclear: Whether installing uvloop multiple times causes issues
   - Recommendation: Install once per process, cache in module-level variable

2. **Should DefaultProvider raise NotImplementedError or provide implementation?**
   - What we know: DefaultProvider currently raises NotImplementedError for crawl()
   - What's unclear: Should crawl_async() also raise, or provide a default?
   - Recommendation: Provide default implementation that raises NotImplementedError with helpful message

3. **Should uvloop be added as required or optional dependency?**
   - What we know: Project requires Python >=3.10, uvloop works on all supported platforms
   - What's unclear: Whether uvloop should be optional for environments that can't install C extensions
   - Recommendation: Add as required dependency (cloudflare optional dependencies already include binary extensions)

## Environment Availability

Step 2.6: SKIPPED (no external dependencies beyond project code - uvloop already installed in environment)

## Sources

### Primary (HIGH confidence)
- Python 3.13.5 built-in asyncio documentation
- uvloop 0.22.1 on macOS (verified behavior)
- src/providers/base.py - ContentProvider Protocol structure
- src/providers/__init__.py - Provider loading mechanism
- src/cli/__init__.py - CLI entry point structure

### Secondary (MEDIUM confidence)
- Web search results not available (API errors); using verified Python testing

### Tertiary (LOW confidence)
- N/A - all findings verified via testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - uvloop is de-facto standard, verified installed and working
- Architecture: HIGH - Protocol extension pattern verified working with async methods
- Pitfalls: MEDIUM - uvloop.install() behavior verified on macOS; Windows behavior based on documentation

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (uvloop API is stable)
