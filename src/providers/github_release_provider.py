"""GitHub release provider for monitoring repository releases.

Handles GitHub repository URLs and fetches the latest release.
Priority is 200 (higher than GitHubProvider's 100 - tried first for releases).

This provider focuses specifically on release data, allowing the general
GitHubProvider to handle non-release repository URLs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from github import GithubException, RateLimitExceededException

from src.discovery.models import DiscoveredFeed
from src.providers import PROVIDERS
from src.providers.base import Article, FetchedResult, Raw

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

    from src.models import Feed, FeedType

logger = logging.getLogger(__name__)

# Reuse the singleton from utils/github.py
from src.utils.github import _get_github_client  # noqa: E402


class GitHubReleaseProvider:
    """Content provider for GitHub repository releases.

    Detects github.com URLs and fetches the latest release
    using the GitHub API. Higher priority (300) than GitHubProvider (100).
    """

    def match(
        self, url: str, response: Response = None, feed_type: FeedType = None
    ) -> bool:
        """Check if URL is a GitHub repository URL.

        Args:
            url: URL to check.
            response: Optional HTTP response (ignored - URL-only matching).
            feed_type: Optional FeedType to restrict matching. If FeedType.GITHUB_RELEASE, matches GitHub repos.

        Returns:
            True if URL is a GitHub repo URL (github.com with owner/repo path).
        """
        from src.models import FeedType

        # If feed_type is specified and is not GITHUB_RELEASE, reject
        if feed_type is not None and feed_type != FeedType.GITHUB_RELEASE:
            return False

        # Support both HTTPS and SSH formats
        if "github.com" not in url:
            return False

        # SSH format: git@github.com:owner/repo.git
        if url.startswith("git@"):
            import re

            match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
            return bool(match)

        # HTTPS format: https://github.com/owner/repo
        parsed = urlparse(url)
        if parsed.netloc == "github.com":
            parts = parsed.path.strip("/").split("/")
            # Need at least owner/repo (2 parts)
            if len(parts) >= 2:
                return True
        return False

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            300 - highest. GitHub releases must be handled by this provider,
            not fall through to RSS or Webpage providers.
        """
        return 300

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch latest GitHub release for a repository.

        Args:
            feed: Feed object containing url.

        Returns:
            FetchedResult with articles list.
        """
        from src.utils.github import parse_github_url

        try:
            owner, repo = parse_github_url(feed.url)
            client = _get_github_client()
            gh_repo = client.get_repo(f"{owner}/{repo}")
            release = gh_repo.get_latest_release()

            release_data = {
                "tag_name": release.tag_name,
                "name": release.name,
                "body": release.body,
                "html_url": release.html_url,
                "published_at": release.published_at.isoformat()
                if release.published_at
                else None,
            }
            articles = self.parse_articles([release_data])
            logger.debug(
                "GitHubReleaseProvider.fetch_articles(%s) returned release: %s",
                feed.url,
                release_data.get("tag_name"),
            )
            return FetchedResult(articles=articles)
        except RateLimitExceededException as e:
            logger.error("GitHub API rate limited for %s: %s", feed.url, e)
            return FetchedResult(articles=[])
        except GithubException as e:
            logger.error("GitHub API error for %s: %s", feed.url, e)
            return FetchedResult(articles=[])
        except ValueError as e:
            logger.error("Invalid GitHub URL %s: %s", feed.url, e)
            return FetchedResult(articles=[])
        except Exception as e:
            logger.error(
                "GitHubReleaseProvider.fetch_articles(%s) failed: %s", feed.url, e
            )
            return FetchedResult(articles=[])

    def parse_articles(self, entries: list[Raw]) -> list[Article]:
        """Convert GitHub release dicts to Article dicts.

        Args:
            entries: List of GitHub release dicts with tag_name, name, body, etc.

        Returns:
            List of Article dicts.
        """
        articles = []
        for raw in entries:
            # title: tag_name or name
            title = raw.get("tag_name") or raw.get("name")

            # link: html_url
            link = raw.get("html_url")

            # guid: tag_name
            guid = raw.get("tag_name")

            # published_at: published_at
            published_at = raw.get("published_at")

            # description: body (release notes)
            description = raw.get("body")

            # content: None (no additional content for releases)
            content = None

            # author: GitHub release has "author" dict with "login" key
            author = None
            if isinstance(raw.get("author"), dict):
                author = raw.get("author", {}).get("login")
            else:
                author = raw.get("author")

            articles.append(
                Article(
                    title=title,
                    link=link,
                    guid=guid,
                    published_at=published_at,
                    description=description,
                    content=content,
                    author=author,
                    tags="",
                    category="",
                )
            )
        return articles

    def parse_feed(self, url: str, response: Response = None) -> DiscoveredFeed:
        """Validate GitHub repository URL and return as DiscoveredFeed.

        Args:
            url: GitHub repository URL.
            response: Unused for GitHub (PyGithub provides data directly).

        Returns:
            DiscoveredFeed with valid=True if URL is a valid GitHub repo,
            valid=False if validation fails.
        """
        from src.utils.github import parse_github_url

        try:
            owner, repo = parse_github_url(url)
            client = _get_github_client()
            gh_repo = client.get_repo(f"{owner}/{repo}")

            repo_name = gh_repo.full_name or f"{owner}/{repo}"

            return DiscoveredFeed(
                url=url,
                title=repo_name,
                feed_type="github_release",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=True,
            )
        except Exception:
            return DiscoveredFeed(
                url=url,
                title=None,
                feed_type="github_release",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=False,
            )

    def discover(
        self, url: str, response: Response = None, depth: int = 1
    ) -> list[DiscoveredFeed]:
        """Discover feed URLs - GitHub releases don't need additional discovery.

        Args:
            url: Current page URL.
            response: Pre-fetched HTTP response (may be None).
            depth: Current crawl depth.

        Returns:
            Empty list - GitHub releases are found via parse_feed() instead.
        """
        return []


# Register this provider - highest priority (300)
PROVIDERS.append(GitHubReleaseProvider())
