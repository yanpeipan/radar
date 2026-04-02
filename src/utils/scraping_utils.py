"""Generic HTML parsing utilities.

This module provides unified fetching utilities with anti-bot mitigation,
caching, and rate limiting. It wraps scrapling's Fetcher and StealthyFetcher
to provide a consistent API for synchronous fetching.

Architecture:
    1. Fast path: Fetcher().get() - uses curl_cffi with browser impersonation,
       suitable for most public websites without anti-bot protection.
    2. Fallback path: StealthyFetcher().fetch() - launches headless Chrome with
       stealth settings, bypasses Cloudflare and other anti-bot measures.

Key features:
    - Automatic fallback from fast to stealth fetcher on block detection
    - URL response caching (5-min TTL) for repeated fetches
    - Per-host rate limiting (1 req/sec default)
    - Selector API support via fetch_selector() for CSS selection

Usage:
    # Get Selector object (for CSS selection)
    selector = fetch_selector("https://example.com")
    articles = selector.css("article.post").all()

    # Get raw HTML response
    response = fetch_with_fallback("https://example.com")
    if response:
        html = response.html_content
"""

from __future__ import annotations

import asyncio
import logging
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

# Per-host semaphore for concurrency control (limits concurrent requests per host)
_host_semaphores: dict[str, asyncio.Semaphore] = {}
_semaphore_lock = asyncio.Lock()  # Only protects _host_semaphores dict

# Per-host sliding window rate limiter: max 1 req/sec per host by default
_host_rate_limits: dict[str, float] = {}
_rate_limit_lock = asyncio.Lock()
_DEFAULT_RATE_LIMIT = 1.0  # seconds between requests per host

# Default max concurrent requests per host
_DEFAULT_MAX_CONCURRENT = 5

# ============================================================================
# Block Detection
# ============================================================================


def _looks_like_block_page(html_content: str | None) -> bool:
    """Check if HTML content looks like a block/challenge page.

    Detects anti-bot blocking by checking for:
    - Empty or very small content (< 1000 bytes)
    - Common challenge page patterns

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


# ============================================================================
# Proxy Configuration
# ============================================================================


def _get_proxy() -> str | None:
    """Get proxy URL from environment variables.

    Returns HTTP_PROXY, HTTPS_PROXY, or ALL_PROXY in that order of preference.
    Converts SOCKS5 to HTTP proxy if needed (Playwright doesn't support SOCKS5 directly).

    Returns:
        Proxy URL string or None if no proxy is configured.
    """
    import os

    for var in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        proxy = os.environ.get(var) or os.environ.get(var.lower())
        if proxy:
            # StealthyFetcher (Playwright) doesn't support SOCKS5 proxy directly
            # If ALL_PROXY is SOCKS5, try to use HTTP_PROXY/HTTPS_PROXY instead
            if proxy.startswith("socks5://"):
                # SOCKS5 not supported, skip
                continue
            return proxy
    return None


# ============================================================================
# Fetcher Configuration
# ============================================================================

# Default fetcher settings - used by both Fetcher.get() and StealthyFetcher.fetch()
# See scrapling docs for full parameter descriptions:
# - Fetcher.get(): curl_cffi-based, fast, impersonates Chrome
# - StealthyFetcher.fetch(): headless Chrome, bypasses anti-bots

# Browser impersonation level for Fetcher.get()
# Options: "chrome", "firefox", "safari", "edge" or specific version strings
_IMPERSONATE = "chrome"

# Fetcher.get() timeout in seconds (passed to curl_cffi)
_BASIC_FETCH_TIMEOUT = 10

# StealthyFetcher.fetch() timeout in milliseconds
# Note: StealthyFetcher uses ms, not seconds!
# Reduced from 30000ms to 15000ms because without network_idle=True,
# pages load much faster (no waiting for external resources to finish)
_STEALTH_TIMEOUT_MS = 15000

# Stealth fetcher settings - enabled when basic fetcher is blocked
# These settings help bypass Cloudflare, hCaptcha, and other anti-bot systems
_STEALTH_SETTINGS = {
    # Disable images/fonts/stylesheets for speed, they don't affect CSS selection
    "disable_resources": True,
    # DO NOT wait for network to be idle - waiting for all connections to finish
    # causes timeouts when external resources (ads, analytics, fonts) are blocked
    # or slow to resolve. The page content is already loaded after 'load' event.
    "network_idle": False,
    # Add random noise to canvas to prevent fingerprinting
    "hide_canvas": True,
    # Prevent WebRTC from leaking local IP (important when using proxy)
    "block_webrtc": True,
    # Use real Chrome browser if installed (more realistic fingerprint)
    "real_chrome": False,  # Disabled by default - requires Chrome installation
    # Solve Cloudflare Turnstile challenges automatically
    "solve_cloudflare": True,
    # Set Google referer header (some sites require this)
    "google_search": True,
    # Wait after page load to ensure JS executes
    "wait": 500,  # ms
}


# Page action for stealth fetcher - scroll to bottom to trigger lazy loading
# This must be a Python callable that accepts a Playwright page object
def _scroll_page(page):
    """Scroll page to bottom to trigger lazy loading."""
    page.evaluate(
        """
        async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 100;
                const timer = setInterval(() => {
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= document.body.scrollHeight - window.innerHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }
        """
    )


# ============================================================================
# Sync Fetching (Core)
# ============================================================================


def _sync_fetch_with_fallback(
    url: str,
    headers: dict | None = None,
    timeout: int | None = None,
    stealth_timeout: int | None = None,
) -> Response | None:
    """Fetch URL with automatic fallback from fast Fetcher to stealth Chrome.

    Strategy:
        1. Try Fetcher().get() with Chrome impersonation - fast, handles most sites
        2. If blocked (403/429) or content looks like block page,
           fall back to StealthyFetcher().fetch() - slower but bypasses anti-bots

    Args:
        url: URL to fetch.
        headers: Optional HTTP headers (uses BROWSER_HEADERS if None).
        timeout: Request timeout in seconds for basic Fetcher.
            Defaults to BASIC_FETCH_TIMEOUT (10s).
        stealth_timeout: Timeout in milliseconds for stealth fetcher.
            Defaults to STEALTH_TIMEOUT_MS (30000ms = 30s).

    Returns:
        Response object with .html_content, .status, etc., or None on failure.
    """
    from scrapling import Fetcher, StealthyFetcher

    if headers is None:
        from src.constants import BROWSER_HEADERS

        headers = BROWSER_HEADERS

    if timeout is None:
        timeout = _BASIC_FETCH_TIMEOUT

    if stealth_timeout is None:
        stealth_timeout = _STEALTH_TIMEOUT_MS

    # -------------------------------------------------------------------
    # Fast path: try basic Fetcher with Chrome impersonation
    # -------------------------------------------------------------------
    try:
        fetcher = Fetcher()
        response = fetcher.get(
            url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            stealthy_headers=True,
            impersonate=_IMPERSONATE,
        )
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

    # -------------------------------------------------------------------
    # Fallback: try stealth fetcher (slower but bypasses most anti-bots)
    # -------------------------------------------------------------------
    try:
        stealth = StealthyFetcher()
        proxy = _get_proxy()
        fetch_kwargs = {
            "headers": headers,
            "timeout": stealth_timeout,
            "page_action": _scroll_page,
            "follow_redirects": True,
            **_STEALTH_SETTINGS,
        }
        if proxy:
            fetch_kwargs["proxy"] = proxy
        return stealth.fetch(url, **fetch_kwargs)
    except Exception as e:
        _logger.warning(f"Stealth fetcher also failed for {url}: {e}")
        return None


# Backward-compatible alias
fetch_with_fallback = _sync_fetch_with_fallback


def fetch_selector(url: str, headers: dict | None = None) -> Selector | None:
    """Fetch a URL and return a Selector object for CSS selection.

    This is the primary entry point for HTML parsing in this codebase.
    Use this when you need to select elements with CSS selectors.

    The returned Selector provides methods like:
        - .css("article.post").all()  -> list of matching elements
        - .css_first("h1.title")      -> first match or None
        - .find("a[href]")             -> find with BeautifulSoup-like API

    Args:
        url: URL to fetch and parse.
        headers: Optional HTTP headers (uses BROWSER_HEADERS if None).

    Returns:
        Selector object for CSS/DOM manipulation, or None if fetch failed.

    Example:
        selector = fetch_selector("https://github.com/trending")
        if selector:
            repos = selector.css("article.Box-row").all()
            for repo in repos:
                name = repo.css_first("h2 a").text
                desc = repo.css_first("p").text
    """
    response = _sync_fetch_with_fallback(url, headers=headers)
    if response is None:
        return None

    # Import here to avoid circular imports
    from scrapling import Selector

    try:
        # Response body is bytes, decode to HTML string
        html = response.html_content
        if isinstance(html, bytes):
            html = html.decode("utf-8", errors="replace")
        selector = Selector(html)
        _logger.debug(f"Successfully parsed HTML selector for {url}")
        return selector
    except Exception as e:
        _logger.warning(f"Failed to parse HTML from response for {url}: {e}")
        return None


# ============================================================================
# Async Fetching with Caching and Rate Limiting
# ============================================================================


async def _rate_limit_host(
    url: str, rate_limit: float | None = None
) -> asyncio.Semaphore:
    """Enforce per-host rate limit using semaphore concurrency control.

    Uses a per-host semaphore to limit concurrent requests (default: 5).
    This allows multiple requests to be in-flight simultaneously without
    convoying through a global lock.

    Args:
        url: URL to extract host from for rate limiting.
        rate_limit: Ignored (semaphore provides concurrency control).

    Returns:
        The acquired semaphore. Caller MUST call sem.release() after fetch.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host:
        return None

    # Get or create per-host semaphore
    async with _semaphore_lock:
        if host not in _host_semaphores:
            _host_semaphores[host] = asyncio.Semaphore(_DEFAULT_MAX_CONCURRENT)
        sem = _host_semaphores[host]

    # Acquire semaphore (blocks if max concurrent requests reached)
    _logger.debug(
        f"Rate limiting {host}: acquiring semaphore (max {_DEFAULT_MAX_CONCURRENT} concurrent)"
    )
    await sem.acquire()
    _logger.debug(f"Rate limiting {host}: semaphore acquired")
    return sem


async def _fetch_with_fallback_async(
    url: str,
    headers: dict | None,
    timeout: int,
) -> Response | None:
    """Async wrapper for fetch_with_fallback with caching.

    Caches responses for 5 minutes to reduce redundant requests.
    Uses per-URL locks to prevent cache stampede (multiple concurrent
    requests to same URL).

    Args:
        url: URL to fetch.
        headers: Optional HTTP headers.
        timeout: Request timeout in seconds.

    Returns:
        Cached or fresh Response object, or None on failure.
    """
    # Check cache first
    cache_key = url
    cached = _url_cache.get(cache_key)
    if cached is not None:
        _logger.debug(f"Cache hit for {url}")
        return cached

    _logger.debug(f"Cache miss for {url}, fetching...")

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
        result = await asyncio.to_thread(
            _sync_fetch_with_fallback, url, headers, timeout
        )

        # Store in cache if successful
        if result is not None:
            _url_cache[cache_key] = result

        return result


async def async_fetch_with_fallback(
    url: str,
    headers: dict | None = None,
    timeout: int = 10,
    rate_limit: float | None = None,
) -> Response | None:
    """Async fetch with caching and rate limiting.

    Fetches a URL with automatic fallback from basic Fetcher to stealth fetcher,
    with URL response caching (5-min TTL) and per-host rate limiting.

    Use this for concurrent fetching of multiple URLs.

    Args:
        url: URL to fetch.
        headers: Optional HTTP headers (uses BROWSER_HEADERS if None).
        timeout: Request timeout in seconds.
        rate_limit: Override default rate limit (1.0 sec) for this call.
            Use higher values (e.g., 5.0) for parallel probing of feed paths.

    Returns:
        Response object with .html_content, .status, etc., or None on failure.
    """
    from src.constants import BROWSER_HEADERS

    if headers is None:
        headers = BROWSER_HEADERS

    # Rate limit per host before fetch (semaphore controls concurrency)
    sem = await _rate_limit_host(url, rate_limit=rate_limit)

    try:
        _logger.debug(f"Fetching {url} with timeout={timeout}s")
        return await _fetch_with_fallback_async(url, headers, timeout)
    finally:
        # Release semaphore after fetch completes
        if sem is not None:
            sem.release()
            _logger.debug(f"Rate limit released for {urlparse(url).netloc.lower()}")


# ============================================================================
# HTML/Response Utilities
# ============================================================================


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

    Some pages use <base href> to set a different base URL for relative links.
    This function extracts it for resolving relative URLs correctly.

    Args:
        page: Parsed HTML page (scrapling Selector).

    Returns:
        Base href URL or None if not present.
    """
    head = page.find("head")
    if head:
        base_tag = head.find("base[href]")
        if base_tag:
            return base_tag.attrib["href"]
    return None
