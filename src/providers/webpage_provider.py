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
from typing import List, Optional

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, CrawlResult, Raw

logger = logging.getLogger(__name__)





# ── Link discovery (generic fallback) ─────────────────────────────────────────

def _root_domain(domain: str) -> str:
    """Return root domain, e.g. 'example.com' from 'www.example.com'."""
    parts = domain.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()


def _discover_links(root, page_url: str) -> List[tuple[str, int]]:
    """Score all internal links on the rendered page.

    Returns list of (url, score) sorted by score descending.
    """
    from urllib.parse import urljoin, urlparse

    base_root = _root_domain(urlparse(page_url).netloc)
    seen: set[str] = set()
    results: dict[str, int] = {}

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

        path = parsed.path.rstrip("/")
        if not path or path in seen:
            continue
        seen.add(path)

        score = 0
        pl = path.lower()

        # Positive signals
        if re.search(r"/[0-9a-f-]{8,}", pl):
            score += 30  # UUID / long-slug pattern
        elif "/article/" in pl:
            score += 25
        elif "/post" in pl:
            score += 20
        elif any(x in pl for x in ["/a/", "/news/", "/story/", "/entry/"]):
            score += 15
        elif re.search(r"/\d+/?$", pl):
            score += 10

        # Negative signals
        if any(x in pl for x in [
            "/tag/", "/category/", "/author/",
            "/page/", "/feed", "/assets/",
            "/static/", "/images/",
            "/login", "/register",
            "/search", "/subscribe",
            "/short_urls/", "/agreement/",
        ]):
            score -= 30

        if score > 0:
            results[full_url] = score

    return sorted(results.items(), key=lambda x: x[1], reverse=True)


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
    from scrapling import StealthyFetcher, Selector

    try:
        fetcher = StealthyFetcher()
        r = fetcher.fetch(url, timeout=30000)
    except ModuleNotFoundError:
        raise  # Re-raise so caller can handle with specific message
    except Exception:
        return {}

    body = r.body.decode("utf-8", errors="replace") if isinstance(r.body, bytes) else str(r.body)
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

        path = parsed.path.rstrip("/")
        if not path:
            continue

        # Build all path prefixes
        segments = path.split("/")
        for i in range(1, len(segments) + 1):
            prefix = "/" + "/".join(segments[:i])
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
        from src.storage import get_feed as storage_get_feed
        from src.models import FeedMetaData
        feed = storage_get_feed(url)
        if feed and feed.metadata:
            data = json.loads(feed.metadata)
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

    def match(self, url: str) -> bool:
        if not url.startswith("http"):
            return False
        lower = url.lower()
        if any(ext in lower for ext in (".rss", ".atom", "/feed", "/feed.xml",
                                         "/atom.xml", "/rss.xml", "/index.xml")):
            return False
        return True

    def priority(self) -> int:
        return 100

    def _df(self):
        if not self._df_initialized:
            from scrapling import DynamicFetcher
            self._DynamicFetcher = DynamicFetcher
            self._df_initialized = True
        return self._DynamicFetcher

    def crawl(self, url: str) -> List[Raw]:
        """Crawl using generic link discovery + Trafilatura extraction."""
        try:
            return self._crawl_discovery(url)
        except Exception as e:
            logger.error("WebpageProvider.crawl(%s) failed: %s", url, e)
            return []

    def _crawl_discovery(self, url: str) -> List[Raw]:
        """Generic fallback: discover article links → Trafilatura on each."""
        from scrapling import DynamicFetcher, Selector
        from trafilatura import extract

        Fetcher = self._df()
        fetcher = Fetcher()

        try:
            r = fetcher.fetch(url, timeout=30000)
        except Exception:
            return []

        body = r.body.decode("utf-8", errors="replace") if isinstance(r.body, bytes) else str(r.body)
        root = Selector(body)

        scored_links = _discover_links(root, url)
        if not scored_links:
            return []

        # Apply path filters from feed metadata
        selectors = _load_feed_selectors(url)
        if selectors:
            link_urls = [url for url, _ in scored_links]
            filtered_urls = _filter_links_by_paths(link_urls, selectors)
            filtered_set = set(filtered_urls)
            scored_links = [(url, score) for url, score in scored_links if url in filtered_set]

        results = []
        for article_url, _ in scored_links[:20]:
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

            results.append({
                "title": title,
                "link": article_url,
                "pub_date": date or datetime.now().strftime("%Y-%m-%d"),
                "tags": [],
                "description": (description or "")[:500] if description else None,
                "content": text,
                "source_url": article_url,
            })

        return results

    def _fetch_page(self, url: str) -> Optional[str]:
        Fetcher = self._df()
        try:
            r = Fetcher().fetch(url, timeout=30000)
            return r.body.decode("utf-8", errors="replace") if isinstance(r.body, bytes) else str(r.body)
        except Exception:
            return None

    async def crawl_async(self, url: str, etag: Optional[str] = None,
                          last_modified: Optional[str] = None) -> CrawlResult:
        import asyncio
        _ = etag, last_modified
        loop = asyncio.get_running_loop()
        try:
            entries = await loop.run_in_executor(None, self.crawl, url)
        except Exception as e:
            logger.error("crawl_async(%s) failed: %s", url, e)
            entries = []
        return CrawlResult(entries=entries)

    def parse(self, raw: Raw) -> Article:
        from src.utils import generate_article_id
        title = raw.get("title")
        link = raw.get("link")
        guid = generate_article_id(raw) if not link else link
        pub_date = raw.get("pub_date")
        description = raw.get("description")
        content = raw.get("content") or raw.get("description")
        return Article(
            title=title, link=link, guid=guid,
            pub_date=pub_date, description=description, content=content,
        )

    def feed_meta(self, url: str) -> "Feed":
        from src.models import Feed
        from src.application.config import get_timezone
        from trafilatura import extract

        # Try Trafilatura on the page itself to extract title
        page_body = self._fetch_page(url)
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
                    if data.get("title"):
                        now = datetime.now(get_timezone()).isoformat()
                        return Feed(
                            id="", name=data["title"], url=url,
                            etag=None, last_modified=None,
                            last_fetched=now, created_at=now,
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

        # Fallback: use page <title>
        from scrapling import DynamicFetcher, Selector
        try:
            r = self._df()().fetch(url, timeout=30000)
            body = r.body.decode("utf-8", errors="replace") if isinstance(r.body, bytes) else str(r.body)
            root = Selector(body)
            title_els = root.css("title")
            title = title_els[0].text.strip() if title_els and title_els[0].text else url
            title = re.sub(r"\s*[-–|]\s*[^-|]+$", "", title).strip()
        except Exception:
            title = url

        now = datetime.now(get_timezone()).isoformat()
        return Feed(id="", name=title, url=url, etag=None,
                     last_modified=None, last_fetched=now, created_at=now)


PROVIDERS.append(WebpageProvider())
