"""GitHub Trending repositories provider.

Handles github.com/trending URLs, fetching daily/weekly/monthly trending repos.
Single feed fetches all 3 periods and returns combined articles with proper GUIDs.

Usage:
    feedship feed add https://github.com/trending
"""

from __future__ import annotations

import logging
import urllib.parse
from typing import TYPE_CHECKING

from src.discovery.models import DiscoveredFeed
from src.providers import PROVIDERS
from src.providers.base import Article, FetchedResult
from src.utils.scraping_utils import fetch_selector

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

    from src.models import Feed, FeedType

logger = logging.getLogger(__name__)

# GitHub Trending URLs for each period
TRENDING_URLS = {
    "daily": "https://github.com/trending?since=daily",
    "weekly": "https://github.com/trending?since=weekly",
    "monthly": "https://github.com/trending?since=monthly",
}

# CSS selectors for GitHub Trending page
TRENDING_SELECTORS = {
    "article": "article.Box-row",
    "repo_link": "h2 a",
    "description": "p",
    "language": "span[itemprop='programmingLanguage']",
    "stars": "a.Link--muted:nth-of-type(1)",
    "forks": "a.Link--muted:nth-of-type(2)",
}


class GitHubTrendingProvider:
    """Content provider for GitHub Trending repositories.

    Detects github.com/trending URLs and fetches trending repos
    for daily, weekly, and monthly periods.
    """

    def match(
        self, url: str, response: Response = None, feed_type: FeedType = None
    ) -> bool:
        """Check if URL is a GitHub Trending URL.

        Args:
            url: URL to check.
            response: Optional HTTP response (ignored - URL-only matching).
            feed_type: Optional FeedType to restrict matching.

        Returns:
            True if URL contains 'github.com/trending'.
        """
        from src.models import FeedType

        # If feed_type is specified and is not GITHUB_TRENDING, reject
        if feed_type is not None and feed_type != FeedType.GITHUB_TRENDING:
            return False

        # URL-only matching for performance
        return "github.com/trending" in url

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            300 - same as GitHubReleaseProvider.
        """
        return 300

    def _parse_period_from_url(self, url: str) -> str | None:
        """Parse the period from a GitHub trending URL's query parameters.

        Args:
            url: GitHub trending URL to parse.

        Returns:
            'daily', 'weekly', 'monthly' if valid since= value found, else None.
        """
        try:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            since_values = params.get("since", [])
            if since_values:
                period = since_values[0].lower()
                if period in ("daily", "weekly", "monthly"):
                    return period
        except Exception:
            pass
        return None

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch trending repositories for specified period or all periods.

        Args:
            feed: Feed object containing url.

        Returns:
            FetchedResult with combined articles from selected period(s).
        """
        articles = []
        seen_guids = set()  # Track seen GUIDs to avoid duplicates

        # Determine which periods to fetch
        period = self._parse_period_from_url(feed.url)
        if period:
            periods_to_fetch = [(period, TRENDING_URLS[period])]
        else:
            periods_to_fetch = list(TRENDING_URLS.items())

        for selected_period, period_url in periods_to_fetch:
            try:
                period_articles = self._fetch_trending_for_period(
                    selected_period, period_url
                )
                # Deduplicate by GUID within this period
                for article in period_articles:
                    if article.guid not in seen_guids:
                        seen_guids.add(article.guid)
                        articles.append(article)
            except Exception as e:
                logger.error(
                    "GitHubTrendingProvider.fetch_articles(%s) failed for %s: %s",
                    feed.url,
                    selected_period,
                    e,
                )

        logger.debug(
            "GitHubTrendingProvider.fetch_articles(%s) returned %d articles",
            feed.url,
            len(articles),
        )
        return FetchedResult(articles=articles)

    def _fetch_trending_for_period(self, period: str, url: str) -> list[Article]:
        """Fetch and parse trending repos for a specific period.

        Args:
            period: Time period (daily, weekly, monthly).
            url: GitHub trending URL for this period.

        Returns:
            List of Article dicts for this period.
        """
        try:
            fetcher = fetch_selector(url)
            if fetcher is None:
                logger.error("Failed to fetch %s", url)
                return []
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return []

        articles = []
        rank = 0

        # Find all repo entries - iterate directly to get Selector objects
        article_selectors = fetcher.css(TRENDING_SELECTORS["article"])
        if not article_selectors:
            logger.warning("No trending repos found at %s", url)
            return []

        for entry in article_selectors:
            rank += 1
            try:
                article = self._parse_repo_entry(entry, period, rank)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning("Failed to parse repo entry: %s", e)
                continue

        return articles

    def _parse_repo_entry(self, entry, period: str, rank: int) -> Article | None:
        """Parse a single repo entry from trending page.

        Args:
            entry: CSS-selected element for a repo.
            period: Time period (daily, weekly, monthly).
            rank: Ranking position (1-based).

        Returns:
            Article dict or None if parsing failed.
        """
        # Extract repo link
        repo_link_el = entry.css(TRENDING_SELECTORS["repo_link"]).first
        if not repo_link_el:
            return None

        repo_path = repo_link_el.css("::attr(href)").get().strip()
        repo_url = f"https://github.com{repo_path}"
        # Extract user/repo from path
        parts = repo_path.strip("/").split("/")
        if len(parts) < 2:
            return None
        user_repo = f"{parts[0]}/{parts[1]}"

        # Extract description
        desc_el = entry.css(TRENDING_SELECTORS["description"]).first
        description = desc_el.text.strip() if desc_el else ""

        # Extract language
        lang_el = entry.css(TRENDING_SELECTORS["language"]).first
        language = lang_el.text.strip() if lang_el else ""

        # Extract stars - text is like "15,000 stars today"
        stars_el = entry.css(TRENDING_SELECTORS["stars"]).first
        stars_text = stars_el.css("::text").get().strip() if stars_el else "0"
        # Parse number from text (remove commas and non-digits)
        stars = 0
        try:
            stars_str = "".join(c for c in stars_text if c.isdigit() or c == ",")
            if stars_str:
                stars = int(float(stars_str.replace(",", "")))
        except Exception:
            stars = 0

        # Extract forks
        forks_el = entry.css(TRENDING_SELECTORS["forks"]).first
        forks_text = forks_el.css("::text").get().strip() if forks_el else "0"
        forks = 0
        try:
            forks_str = "".join(c for c in forks_text if c.isdigit() or c == ",")
            if forks_str:
                forks = int(float(forks_str.replace(",", "")))
        except Exception:
            forks = 0

        # Build title: [15000★] user/repo: description
        title = f"[{stars}★] {user_repo}: {description}"

        # Build tags: language:Python,stars:15000
        tags = f"language:{language},stars:{stars}" if language else f"stars:{stars}"

        # GUID format: github-trending:{period}:{repo_url}
        guid = f"github-trending:{period}:{repo_url}"

        return Article(
            title=title,
            link=repo_url,
            guid=guid,
            published_at=None,
            description=description,
            content=description,
            tags=tags,
            category="",
            meta={
                "stars": stars,
                "forks": forks,
                "language": language,
                "rank": rank,
                "period": period,
            },
        )

    def parse_feed(self, url: str, response: Response = None) -> DiscoveredFeed:
        """Validate GitHub Trending URL and return as DiscoveredFeed.

        Args:
            url: GitHub Trending URL.
            response: Unused for GitHub Trending.

        Returns:
            DiscoveredFeed with valid=True if URL is a valid trending URL.
        """
        if "github.com/trending" not in url:
            return DiscoveredFeed(
                url=url,
                title=None,
                feed_type="github_trending",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=False,
            )

        return DiscoveredFeed(
            url=url,
            title="GitHub Trending",
            feed_type="github_trending",
            source=f"provider_{self.__class__.__name__}",
            page_url=url,
            valid=True,
        )

    def discover(
        self, url: str, response: Response = None, depth: int = 1
    ) -> list[DiscoveredFeed]:
        """Discover feed URLs - GitHub Trending doesn't need discovery.

        Args:
            url: Current page URL.
            response: Pre-fetched HTTP response (may be None).
            depth: Current crawl depth.

        Returns:
            Empty list - trending URLs are directly parsed.
        """
        return []


# Register this provider - same priority as GitHubReleaseProvider (300)
PROVIDERS.append(GitHubTrendingProvider())
