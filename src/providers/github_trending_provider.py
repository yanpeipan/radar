"""GitHub Trending repositories provider.

Handles github.com/trending URLs, fetching daily/weekly/monthly trending repos.
Single feed fetches all 3 periods and returns combined articles with proper GUIDs.

Usage:
    feedship feed add https://github.com/trending
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from scrapling import Fetcher

from src.discovery.models import DiscoveredFeed
from src.providers import PROVIDERS
from src.providers.base import Article, FetchedResult

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
    "stars": "a.Link--muted:nth-of-type(2)",
    "forks": "a.Link--muted:nth-of-type(3)",
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

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch trending repositories for all periods.

        Args:
            feed: Feed object containing url.

        Returns:
            FetchedResult with combined articles from all periods.
        """
        articles = []
        seen_guids = set()  # Track seen GUIDs to avoid duplicates

        for period, period_url in TRENDING_URLS.items():
            try:
                period_articles = self._fetch_trending_for_period(period, period_url)
                # Deduplicate by GUID within this period
                for article in period_articles:
                    if article["guid"] not in seen_guids:
                        seen_guids.add(article["guid"])
                        articles.append(article)
            except Exception as e:
                logger.error(
                    "GitHubTrendingProvider.fetch_articles(%s) failed for %s: %s",
                    feed.url,
                    period,
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
            fetcher = Fetcher.fetch(url)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return []

        articles = []
        rank = 0

        # Find all repo entries
        repo_entries = fetcher.css(TRENDING_SELECTORS["article"]).all()
        if not repo_entries:
            logger.warning("No trending repos found at %s", url)
            return []

        for entry in repo_entries:
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
        repo_link_el = entry.css_first(TRENDING_SELECTORS["repo_link"])
        if not repo_link_el:
            return None

        repo_path = repo_link_el.css_first("::attr(href)").strip()
        repo_url = f"https://github.com{repo_path}"
        # Extract user/repo from path
        parts = repo_path.strip("/").split("/")
        if len(parts) < 2:
            return None
        user_repo = f"{parts[0]}/{parts[1]}"

        # Extract description
        desc_el = entry.css_first(TRENDING_SELECTORS["description"])
        description = desc_el.text.strip() if desc_el else ""

        # Extract language
        lang_el = entry.css_first(TRENDING_SELECTORS["language"])
        language = lang_el.text.strip() if lang_el else ""

        # Extract stars - text is like "15,000 stars today"
        stars_el = entry.css_first(TRENDING_SELECTORS["stars"])
        stars_text = stars_el.text.strip() if stars_el else "0"
        # Parse number from text (remove commas and non-digits)
        stars_str = "".join(c for c in stars_text if c.isdigit() or c == ",")
        stars = int(stars_str.replace(",", "")) if stars_str else 0

        # Extract forks
        forks_el = entry.css_first(TRENDING_SELECTORS["forks"])
        forks_text = forks_el.text.strip() if forks_el else "0"
        forks_str = "".join(c for c in forks_text if c.isdigit() or c == ",")
        forks = int(forks_str.replace(",", "")) if forks_str else 0

        # Build title: [15000★] user/repo: description
        title = f"[{stars}★] {user_repo}: {description}"

        # Build metadata JSON
        metadata = {
            "stars": stars,
            "forks": forks,
            "language": language,
            "rank": rank,
            "period": period,
        }

        # Build tags: language:Python,stars:15000
        tags = f"language:{language},stars:{stars}" if language else f"stars:{stars}"

        # GUID format: github-trending:{period}:{repo_url}
        guid = f"github-trending:{period}:{repo_url}"

        return Article(
            title=title,
            link=repo_url,
            guid=guid,
            published_at=None,  # No published date for trending
            description=description,
            content=json.dumps(metadata),  # Store metadata in content
            tags=tags,
            category="",
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
