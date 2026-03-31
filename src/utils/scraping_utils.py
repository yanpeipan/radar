"""Generic HTML parsing utilities."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from cachetools import TTLCache

if TYPE_CHECKING:
    from scrapling import Selector
    from scrapling.engines.toolbelt.custom import Response

_logger = logging.getLogger(__name__)

# Block detection: status codes that indicate anti-bot blocking
_BLOCK_STATUS_CODES = {403, 429}
# Block pages typically have very small content
_BLOCK_CONTENT_MIN_BYTES = 1000

# URL response cache: 1000 URLs, 5-min TTL per entry
_url_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)
# Per-URL locks to prevent cache stampede
_url_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()  # Protects _url_locks dict creation

# Per-host sliding window rate limiter: max 1 req/sec per host by default
_host_rate_limits: dict[str, deque] = {}
_rate_limit_lock = asyncio.Lock()
_DEFAULT_RATE_LIMIT = 1.0  # seconds between requests per host


def _looks_like_block_page(html_content: str | None) -> bool:
    """Check if HTML content looks like a block/challenge page.

    Args:
        html_content: HTML string to check.

    Returns:
        True if content appears to be a block page (very small or empty).
    """
    if not html_content:
        return True
    # Only consider it a block page if content is very small
    # (genuine pages typically have >10KB of content)
    return len(html_content) < _BLOCK_CONTENT_MIN_BYTES


def _sync_fetch_with_fallback(
    url: str,
    headers: dict | None = None,
    timeout: int = 10,
    stealth_timeout: int | None = None,
) -> Response | None:
    """Sync fetch with fallback (no caching). Internal use only.

    Strategy:
        1. Try Fetcher().get() - fast, works for most sites
        2. If blocked (403/429) or content looks like block page,
           fall back to StealthyFetcher().fetch() - slower but bypasses bots

    Args:
        url: URL to fetch.
        headers: Optional HTTP headers (uses BROWSER_HEADERS if None).
        timeout: Request timeout in seconds for basic Fetcher.
        stealth_timeout: Timeout in milliseconds for stealth fetcher.
            Defaults to timeout * 1000 (same as basic fetcher but in ms).

    Returns:
        Response object with .html_content, .status, etc., or None on failure.
    """
    from scrapling import Fetcher, StealthyFetcher

    if headers is None:
        from src.constants import BROWSER_HEADERS

        headers = BROWSER_HEADERS

    # Default stealth timeout to timeout * 1000 (convert seconds to ms)
    if stealth_timeout is None:
        stealth_timeout = timeout * 1000

    # Fast path: try basic Fetcher
    try:
        fetcher = Fetcher()
        response = fetcher.get(url, headers=headers, timeout=timeout)
        status = getattr(response, "status", 0)
        html = getattr(response, "html_content", None) or ""

        if status in _BLOCK_STATUS_CODES or _looks_like_block_page(html):
            _logger.debug(
                f"Basic fetch blocked ({status}), trying stealth fetcher for {url}"
            )
        else:
            return response
    except Exception as e:
        _logger.debug(f"Basic fetch failed ({e}), trying stealth fetcher for {url}")

    # Fallback: try stealth fetcher (slower but bypasses most anti-bots)
    # Use configurable timeout for stealth fetcher (handles JS rendering)
    try:
        stealth = StealthyFetcher()
        return stealth.fetch(url, headers=headers, timeout=stealth_timeout)
    except Exception as e:
        _logger.warning(f"Stealth fetcher also failed for {url}: {e}")
        return None


# Backward-compatible alias
fetch_with_fallback = _sync_fetch_with_fallback


async def _rate_limit_host(url: str, rate_limit: float = _DEFAULT_RATE_LIMIT) -> None:
    """Enforce per-host rate limit using sliding window."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host:
        return

    now = asyncio.get_event_loop().time()

    async with _rate_limit_lock:
        if host not in _host_rate_limits:
            _host_rate_limits[host] = deque()

        window = _host_rate_limits[host]

        # Remove timestamps outside the sliding window
        while window and now - window[0] >= rate_limit:
            window.popleft()

        # If window is full, sleep until oldest entry expires
        if len(window) >= 1:
            sleep_time = rate_limit - (now - window[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                # Clean up again after sleep
                now = asyncio.get_event_loop().time()
                while window and now - window[0] >= rate_limit:
                    window.popleft()

        # Add current timestamp
        window.append(now)


async def _fetch_with_fallback_async(
    url: str,
    headers: dict | None,
    timeout: int,
) -> Response | None:
    """Async wrapper for fetch_with_fallback with caching."""
    # Check cache first
    cache_key = url
    cached = _url_cache.get(cache_key)
    if cached is not None:
        _logger.debug(f"Cache hit for {url}")
        return cached

    # Get or create per-URL lock
    async with _locks_lock:
        if url not in _url_locks:
            _url_locks[url] = asyncio.Lock()
        lock = _url_locks[url]

    # Fetch with lock to prevent stampede
    async with lock:
        # Double-check cache (another coroutine may have populated it)
        cached = _url_cache.get(cache_key)
        if cached is not None:
            return cached

        # Perform actual fetch (run sync function in thread)
        result = await asyncio.to_thread(_sync_fetch_with_fallback, url, headers, timeout)

        # Store in cache if successful
        if result is not None:
            _url_cache[cache_key] = result

        return result


async def async_fetch_with_fallback(
    url: str,
    headers: dict | None = None,
    timeout: int = 10,
) -> Response | None:
    """Async fetch with caching and rate limiting.

    Fetches a URL with automatic fallback from basic Fetcher to stealth fetcher,
    with URL response caching (5-min TTL) and per-host rate limiting.

    Args:
        url: URL to fetch.
        headers: Optional HTTP headers (uses BROWSER_HEADERS if None).
        timeout: Request timeout in seconds.

    Returns:
        Response object with .html_content, .status, etc., or None on failure.
    """
    from src.constants import BROWSER_HEADERS

    if headers is None:
        headers = BROWSER_HEADERS

    # Rate limit per host before fetch
    await _rate_limit_host(url)

    return await _fetch_with_fallback_async(url, headers, timeout)


def parse_html_body(response: Response) -> str | None:
    """Parse HTML body from HTTP response.

    Args:
        response: HTTP response object with .body attribute.

    Returns:
        HTML string or None if not available.
    """
    if not response:
        return None
    try:
        if response.body:
            return (
                response.body.decode("utf-8", errors="replace")
                if isinstance(response.body, bytes)
                else str(response.body)
            )
    except Exception:
        pass
    return None


def find_base_href(page: Selector) -> str | None:
    """Extract <base href> override from page head.

    Args:
        page: Parsed HTML page (scrapling Selector).

    Returns:
        Base href URL or None.
    """
    head = page.find("head")
    if head:
        base_tag = head.find("base[href]")
        if base_tag:
            return base_tag.attrib["href"]
    return None
