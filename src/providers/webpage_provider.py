"""Webpage provider - generic JS-rendered page extractor.

Uses StealthyFetcher for link analysis, DynamicFetcher for JS rendering,
and Trafilatura for article extraction.

Strategy:
  1. Fetch page with StealthyFetcher/DynamicFetcher
  2. Discover article links via scoring heuristics
  3. Apply path filters from feed metadata (if set)
  4. Extract content with Trafilatura
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from src.discovery.models import DiscoveredFeed
from src.providers import PROVIDERS
from src.providers.base import Article, FetchedResult, Raw

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

    from src.models import Feed, FeedType

logger = logging.getLogger(__name__)


# ── Link discovery (generic fallback) ─────────────────────────────────────────


def _root_domain(domain: str) -> str:
    """Return root domain, e.g. 'example.com' from 'www.example.com'."""
    parts = domain.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()


def _discover_links(root, page_url: str) -> list[tuple[str, int]]:
    """Count internal links by path and return sorted by count descending."""
    from urllib.parse import urljoin, urlparse

    base_root = _root_domain(urlparse(page_url).netloc)
    path_counts: dict[str, int] = {}

    for el in root.css("a[href]"):
        href = el.attrib.get("href", "").strip()
        if not href or href.startswith("#") or "javascript:" in href.lower():
            continue

        full_url = urljoin(page_url, href)
        parsed = urlparse(full_url)
        if not parsed.netloc:
            continue

        link_root = _root_domain(parsed.netloc)
        if link_root != base_root:
            continue

        path = re.sub(r"//+", "/", parsed.path).rstrip("/")
        if not path:
            continue

        path_counts[path] = path_counts.get(path, 0) + 1

    return sorted(path_counts.items(), key=lambda x: x[1], reverse=True)


# ── Path analysis for link filtering ─────────────────────────────────────────


def _analyze_link_paths(url: str, limit: int = 15) -> dict[str, int]:
    """Analyze all links on a page and return path patterns with their counts.

    Uses StealthyFetcher to get JS-rendered content, extracts all href attributes,
    then builds path prefix patterns (e.g. /articles/2026-02-02/1 → /articles,
    /articles/2026-02-02, /articles/2026-02-02/1) and counts them.

    Args:
        url: Page URL to analyze.
        limit: Max number of path patterns to return.

    Returns:
        Dict of path_pattern -> count, sorted by count descending.
    """
    from urllib.parse import urljoin, urlparse

    from scrapling import Selector

    from src.utils.scraping_utils import fetch_with_fallback

    try:
        r = fetch_with_fallback(url, timeout=30)
        if r is None:
            return {}
    except Exception:
        return {}

    body = (
        r.body.decode("utf-8", errors="replace")
        if isinstance(r.body, bytes)
        else str(r.body)
    )
    root = Selector(body)

    path_counts: dict[str, int] = {}
    base_netloc = urlparse(url).netloc.lower()

    for el in root.css("a[href]"):
        href = el.attrib.get("href", "").strip()
        if not href or href.startswith("#") or "javascript:" in href.lower():
            continue

        full_url = urljoin(url, href)
        parsed = urlparse(full_url)

        # Only same-domain links
        if parsed.netloc.lower() != base_netloc:
            continue

        path = re.sub(r"//+", "/", parsed.path).rstrip("/")
        if not path:
            continue

        # Build all path prefixes
        segments = path.split("/")
        for i in range(1, len(segments) + 1):
            prefix = "/".join(segments[:i]) or "/"
            path_counts[prefix] = path_counts.get(prefix, 0) + 1

    # Sort by count descending
    sorted_paths = dict(
        sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    )
    return sorted_paths


def _filter_links_by_paths(links: list[str], allowed_paths: list[str]) -> list[str]:
    """Filter links to only those whose path starts with an allowed prefix.

    Args:
        links: List of URLs to filter.
        allowed_paths: List of path prefixes to keep.

    Returns:
        Filtered list of URLs.
    """
    from urllib.parse import urlparse

    if not allowed_paths:
        return links

    allowed_lower = [p.lower() for p in allowed_paths]
    filtered = []
    for link in links:
        path = urlparse(link).path.rstrip("/").lower()
        if any(path.startswith(p) for p in allowed_lower):
            filtered.append(link)
    return filtered


def _load_feed_selectors(url: str) -> list[str]:
    """Load selectors from feed metadata for a given URL.

    Args:
        url: Feed URL to look up.

    Returns:
        List of path filter prefixes, or empty list if none found.
    """
    import json

    try:
        import sqlite3

        from src.models import FeedMetaData
        from src.storage.sqlite.impl import get_db_path

        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT metadata FROM feeds WHERE url = ?", (url,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            data = json.loads(row[0])
            meta = FeedMetaData(**data)
            return meta.selectors or []
    except Exception:
        pass
    return []


# ── Main provider ─────────────────────────────────────────────────────────────


class WebpageProvider:
    """Generic web page provider using DynamicFetcher + Trafilatura.

    Falls back to DefaultProvider (priority=0) when this provider returns nothing.
    """

    def __init__(self) -> None:
        self._df_initialized = False

    def match(
        self, url: str, response: Response = None, feed_type: FeedType = None
    ) -> bool:
        """Check if URL is a webpage (not a direct feed URL).

        Args:
            url: URL to check.
            response: Optional HTTP response (ignored - URL-only matching).
            feed_type: Optional FeedType (ignored).

        Returns:
            True if URL looks like a webpage (not a feed URL).
        """
        if not url.startswith("http"):
            return False
        lower = url.lower()
        if any(
            ext in lower
            for ext in (
                ".rss",
                ".atom",
                "/feed",
                "/feed.xml",
                "/atom.xml",
                "/rss.xml",
                "/index.xml",
            )
        ):
            return False
        return False  # 功能还不完善，暂时关闭匹配

    def priority(self) -> int:
        return 100

    def _df(self):
        if not self._df_initialized:
            from scrapling import DynamicFetcher

            self._DynamicFetcher = DynamicFetcher
            self._df_initialized = True
        return self._DynamicFetcher

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch articles using generic link discovery + Trafilatura extraction."""
        try:
            raw_results, new_etag, new_modified = self._crawl_discovery(
                feed.url, etag=feed.etag, modified_at=feed.modified_at
            )
            return FetchedResult(
                articles=self.parse_articles(raw_results),
                etag=new_etag,
                modified_at=new_modified,
            )
        except Exception as e:
            logger.error("WebpageProvider.fetch_articles(%s) failed: %s", feed.url, e)
            return FetchedResult(articles=[])

    def _crawl_discovery(
        self, url: str, etag: str | None = None, modified_at: str | None = None
    ) -> tuple[list[Raw], str | None, str | None]:
        """Generic fallback: discover article links → Trafilatura on each.

        Args:
            url: Page URL to crawl.
            etag: Optional ETag for conditional request.
            modified_at: Optional Last-Modified for conditional request.

        Returns:
            Tuple of (list of Raw article dicts, etag | None, modified_at | None).
        """
        from urllib.parse import urljoin

        from scrapling import Selector
        from trafilatura import extract

        Fetcher = self._df()
        fetcher = Fetcher()

        # Build headers for conditional request
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if modified_at:
            headers["If-Modified-Since"] = modified_at

        try:
            if headers:
                r = fetcher.fetch(url, timeout=30000, headers=headers)
            else:
                r = fetcher.fetch(url, timeout=30000)
        except Exception:
            return [], None, None

        # Handle 304 Not Modified
        if r.status == 304:
            logger.info("WebpageProvider: %s returned 304 Not Modified", url)
            return [], etag, modified_at

        body = (
            r.body.decode("utf-8", errors="replace")
            if isinstance(r.body, bytes)
            else str(r.body)
        )
        root = Selector(body)

        # Extract etag and modified_at from response for next conditional request
        new_etag = (
            getattr(r, "headers", {}).get("etag") if hasattr(r, "headers") else None
        )
        new_modified = (
            getattr(r, "headers", {}).get("last-modified")
            if hasattr(r, "headers")
            else None
        )

        scored_links = _discover_links(root, url)
        if not scored_links:
            return []

        # Apply path filters from feed metadata
        selectors = _load_feed_selectors(url)
        if selectors:
            link_urls = [path for path, _ in scored_links]
            filtered_urls = _filter_links_by_paths(link_urls, selectors)
            filtered_set = set(filtered_urls)
            filtered_links = [
                (path, score) for path, score in scored_links if path in filtered_set
            ]
            # Fallback: if filtering removes all links, use unfiltered
            scored_links = filtered_links if filtered_links else scored_links

        # Convert relative paths to absolute URLs for _fetch_page
        article_urls = [urljoin(url, path) for path, _ in scored_links[:20]]

        results = []
        for article_url in article_urls:
            article_body = self._fetch_page(article_url)
            if not article_body:
                continue

            result = extract(
                article_body,
                url=article_url,
                with_metadata=True,
                output_format="json",
                include_comments=False,
            )
            if not result:
                continue

            try:
                import json

                data = json.loads(result) if isinstance(result, str) else result
            except (json.JSONDecodeError, TypeError):
                continue

            title = data.get("title", "") or article_url
            text = data.get("text", "") or data.get("content", "")
            description = data.get("description", "")
            date = data.get("date", "")

            if not text or len(text) < 100:
                continue

            results.append(
                {
                    "title": title,
                    "link": article_url,
                    "published_at": date or datetime.now().strftime("%Y-%m-%d"),
                    "tags": [],
                    "description": (description or "")[:500] if description else None,
                    "content": text,
                    "source_url": article_url,
                }
            )

        return results, new_etag, new_modified

    def _fetch_page(self, url: str) -> str | None:
        Fetcher = self._df()
        try:
            r = Fetcher().fetch(url, timeout=30000)
            return (
                r.body.decode("utf-8", errors="replace")
                if isinstance(r.body, bytes)
                else str(r.body)
            )
        except Exception:
            return None

    def parse_articles(self, entries: list[Raw]) -> list[Article]:
        from src.utils import generate_article_id

        articles = []
        for raw in entries:
            title = raw.get("title")
            link = raw.get("link")
            guid = link if link else generate_article_id(raw)
            published_at = raw.get("published_at")
            description = raw.get("description")
            content = raw.get("content") or raw.get("description")
            articles.append(
                Article(
                    title=title,
                    link=link,
                    guid=guid,
                    published_at=published_at,
                    description=description,
                    content=content,
                )
            )
        return articles

    def parse_feed(self, url: str, response: Response = None) -> DiscoveredFeed:
        """Validate webpage URL and return as DiscoveredFeed (fallback only).

        Args:
            url: Webpage URL to validate.
            response: Pre-fetched HTTP response (may be None).

        Returns:
            DiscoveredFeed with valid=False (webpage is not a feed).
        """
        from trafilatura import extract

        # Try Trafilatura on the page itself to extract title
        page_body = self._fetch_page(url)
        title = None
        if page_body:
            result = extract(
                page_body,
                url=url,
                with_metadata=True,
                output_format="json",
                include_comments=False,
            )
            if result:
                try:
                    data = json.loads(result) if isinstance(result, str) else result
                    title = data.get("title")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Fallback: use page <title>
        if not title:
            from scrapling import Selector

            try:
                r = self._df()().fetch(url, timeout=30000)
                body = (
                    r.body.decode("utf-8", errors="replace")
                    if isinstance(r.body, bytes)
                    else str(r.body)
                )
                root = Selector(body)
                title_els = root.css("title")
                title = (
                    title_els[0].text.strip()
                    if title_els and title_els[0].text
                    else url
                )
                title = re.sub(r"\s*[-–|]\s*[^-|]+$", "", title).strip()
            except Exception:
                title = url

        return DiscoveredFeed(
            url=url,
            title=title,
            feed_type="webpage",
            source=f"provider_{self.__class__.__name__}",
            page_url=url,
            valid=False,  # Webpage is not a feed, just discovered page
        )

    def discover(
        self, url: str, response: Response = None, depth: int = 1
    ) -> list[DiscoveredFeed]:
        """Discover feed URLs - WebpageProvider is a fallback, no discovery needed.

        Args:
            url: Current page URL.
            response: Pre-fetched HTTP response (may be None).
            depth: Current crawl depth.

        Returns:
            Empty list - WebpageProvider doesn't discover additional feeds.
        """
        return []


PROVIDERS.append(WebpageProvider())
