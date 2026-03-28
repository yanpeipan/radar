"""Webpage provider - generic JS-rendered page extractor.

Uses DynamicFetcher (Playwright) for JS rendering, Trafilatura for article
extraction, and optional CSS-selector configs from config.yaml for list pages.

No Python-level hardcoding. All site-specific rules live in config.yaml.

Strategy per URL type:
  1. List page (feed add / fetch):
     → CSS selector config from config.yaml → extract multiple article entries
     → Fallback: generic link discovery → Trafilatura on each link
  2. Single article URL:
     → DynamicFetcher + Trafilatura → extract title/content/description
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, CrawlResult, Raw

logger = logging.getLogger(__name__)



# ── Config helpers ──────────────────────────────────────────────────────────────

def _load_webpage_sites() -> dict:
    """Load webpage_sites from config.yaml (direct YAML read)."""
    import yaml
    from pathlib import Path
    config_path = Path(__file__).resolve().parent.parent.parent / "config.yaml"
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("webpage_sites", {}) if data else {}
    except Exception:
        return {}


def _site_config_for(url: str) -> dict:
    """Return the matching site's config dict, or {} if none found."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    sites = _load_webpage_sites()
    for site_domain, config in sites.items():
        if site_domain in domain:
            return config
    return {}


def _section_config_for(url: str, site_config: dict) -> dict:
    """Return the most specific section config for a URL path."""
    if not site_config:
        return {}
    from urllib.parse import urlparse
    path = urlparse(url).path.strip("/")
    segment = path.split("/")[0] if path else ""
    if segment and segment in site_config:
        return site_config[segment]
    return site_config.get("_default", {})


# ── Article link construction ────────────────────────────────────────────────

def _construct_article_link(item, section_config: dict) -> Optional[str]:
    """Build article URL from item image URL using link_pattern + link_uuid_regex."""
    pattern = section_config.get("link_pattern")
    uuid_re = section_config.get("link_uuid_regex")
    if not pattern or not uuid_re:
        return None
    for img in item.css("img"):
        src = img.attrib.get("src", "")
        m = re.search(uuid_re, src)
        if m:
            return pattern.replace("{uuid}", m.group(1))
    return None


# ── Date parsing ───────────────────────────────────────────────────────────────

def _parse_date(date_str: str | None, date_format: str | None = None) -> Optional[str]:
    """Parse date string into YYYY-MM-DD.

    Args:
        date_str: Raw date string from page
        date_format: Optional site-specific format pattern (e.g., "CN" for Chinese "X月X日")
                     If None, tries ISO format only.
    """
    if not date_str:
        return None
    date_str = date_str.strip()

    # Site-specific: Chinese "X月X日" format (e.g., "3月28日")
    if date_format == "CN":
        m = re.match(r"(\d{1,2})月(\d{1,2})日", date_str)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            now = datetime.now()
            year = now.year if month <= now.month else now.year - 1
            return datetime(year, month, day).strftime("%Y-%m-%d")

    # Default: ISO format YYYY-MM-DD
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").isoformat()
    except ValueError:
        pass

    return datetime.now().strftime("%Y-%m-%d")


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
        try:
            site_config = _site_config_for(url)
            section_config = _section_config_for(url, site_config)

            # ── Case 1: site has CSS selector config → extract list from rendered page
            if section_config:
                items = self._crawl_list(url, section_config)
                if items:
                    return items

            # ── Case 2: try single-article Trafilatura extraction
            items = self._crawl_article(url)
            if items:
                return items

            # ── Case 3: generic link discovery → fetch each link with Trafilatura
            return self._crawl_discovery(url)
        except Exception as e:
            logger.error("WebpageProvider.crawl(%s) failed: %s", url, e)
            return []

    def _crawl_list(self, url: str, config: dict) -> List[Raw]:
        """Extract article list from rendered page using CSS selectors from config."""
        from scrapling import DynamicFetcher, Selector

        wait_sel = config.get("wait_selector", "article")
        item_sel = config.get("item", "article")
        title_sel = config.get("title")
        time_sel = config.get("time")
        tags_sel = config.get("tags")
        desc_sel = config.get("description")
        date_format = config.get("date_format")

        Fetcher = self._df()
        fetcher = Fetcher()

        try:
            r = fetcher.fetch(url, timeout=30000, wait_selector=wait_sel)
        except Exception as e:
            logger.warning("DynamicFetcher(%s) wait_selector=%s failed: %s, retrying",
                           url, wait_sel, e)
            try:
                r = fetcher.fetch(url, timeout=30000)
            except Exception:
                return []

        body = r.body.decode("utf-8", errors="replace") if isinstance(r.body, bytes) else str(r.body)
        root = Selector(body)

        items = root.css(item_sel)
        logger.debug("WebpageProvider._crawl_list found %d items with '%s'", len(items), item_sel)

        # Load path filters for this feed
        selectors = _load_feed_selectors(url)

        results = []

        for item in items:
            title = None
            if title_sel:
                els = item.css(title_sel)
                title = els[0].text.strip() if els and els[0].text else None

            # Link: explicit selector first, then UUID-from-image construction
            link = None
            link_sel = config.get("link")
            if link_sel:
                els = item.css(link_sel)
                if els:
                    link = els[0].attrib.get("href")
            if not link:
                link = _construct_article_link(item, config)

            pub_date = None
            if time_sel:
                els = item.css(time_sel)
                if els:
                    pub_date = _parse_date(els[0].text, date_format)

            tags = []
            if tags_sel:
                tags = [t.text.strip() for t in item.css(tags_sel) if t.text]

            description = None
            if desc_sel:
                els = item.css(desc_sel)
                if els and els[0].text:
                    description = els[0].text.strip()

            if not title:
                continue

            # Apply path filters if configured
            if link and selectors:
                from urllib.parse import urlparse
                link_path = urlparse(link).path.rstrip("/").lower()
                if not any(link_path.startswith(p.lower()) for p in selectors):
                    continue

            # Try to fetch full article content for this article link
            content = None
            if link:
                article_items = self._crawl_article(link)
                if article_items:
                    content = article_items[0].get("content")
                    if article_items[0].get("description"):
                        description = article_items[0].get("description")

            results.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "tags": tags,
                "description": description,
                "content": content,
                "source_url": url,
            })

        return results

    def _crawl_article(self, url: str) -> List[Raw]:
        """Fetch a single article page using DynamicFetcher + Trafilatura."""
        from scrapling import DynamicFetcher
        from trafilatura import extract

        Fetcher = self._df()
        fetcher = Fetcher()

        try:
            r = fetcher.fetch(url, timeout=30000)
        except Exception:
            return []

        body = r.body.decode("utf-8", errors="replace") if isinstance(r.body, bytes) else str(r.body)

        # Try trafilatura extraction with metadata
        result = extract(
            body,
            url=url,
            with_metadata=True,
            output_format="json",
            include_comments=False,
        )

        if not result:
            return []

        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            # Fallback: result might be just text
            if isinstance(result, str):
                return [{
                    "title": url,
                    "link": url,
                    "pub_date": datetime.now().strftime("%Y-%m-%d"),
                    "tags": [],
                    "description": None,
                    "content": result,
                    "source_url": url,
                }]
            return []

        title = data.get("title", "") or url
        text = data.get("text", "") or data.get("content", "")
        description = data.get("description", "") or data.get("author", "")
        date = data.get("date", "")

        if not text:
            return []

        return [{
            "title": title,
            "link": url,
            "pub_date": date or datetime.now().strftime("%Y-%m-%d"),
            "tags": [],
            "description": (description or "")[:500] if description else None,
            "content": text,
            "source_url": url,
        }]

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

        # First try Trafilatura on the page itself
        items = self._crawl_article(url)
        if items and items[0].get("title"):
            now = datetime.now(get_timezone()).isoformat()
            return Feed(
                id="", name=items[0]["title"], url=url,
                etag=None, last_modified=None,
                last_fetched=now, created_at=now,
            )

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
