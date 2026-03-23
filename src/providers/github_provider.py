"""GitHub provider for monitoring repository releases.

Handles GitHub repository URLs and fetches latest releases.
Priority is 100 (highest - tried first).
"""
from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, Raw, TagParser

logger = logging.getLogger(__name__)


class GitHubProvider:
    """Content provider for GitHub repository releases.

    Detects github.com URLs and fetches the latest release
    using the GitHub API.
    """

    def match(self, url: str) -> bool:
        """Check if URL is a GitHub repository URL.

        Args:
            url: URL to check.

        Returns:
            True if URL is a GitHub repo URL (github.com with owner/repo path).
        """
        # Support both HTTPS and SSH formats
        if "github.com" not in url:
            return False

        # SSH format: git@github.com:owner/repo.git
        if url.startswith("git@"):
            import re
            match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
            if match:
                return True
            return False

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
            100 - highest priority, tried first.
        """
        return 100

    def crawl(self, url: str) -> List[Raw]:
        """Fetch latest GitHub release for a repository.

        Args:
            url: GitHub repository URL.

        Returns:
            List with single release dict, or empty list if no release or error.
        """
        from src.github import fetch_latest_release, parse_github_url, RateLimitError, GitHubAPIError

        try:
            owner, repo = parse_github_url(url)
            release_data = fetch_latest_release(owner, repo)
            if release_data is None:
                logger.info("No releases found for %s/%s", owner, repo)
                return []
            logger.debug("GitHubProvider.crawl(%s) returned release: %s", url, release_data.get("tag_name"))
            return [release_data]
        except RateLimitError as e:
            logger.error("GitHub API rate limited for %s: %s", url, e)
            return []
        except GitHubAPIError as e:
            logger.error("GitHub API error for %s: %s", url, e)
            return []
        except ValueError as e:
            logger.error("Invalid GitHub URL %s: %s", url, e)
            return []
        except Exception as e:
            logger.error("GitHubProvider.crawl(%s) failed: %s", url, e)
            return []

    def parse(self, raw: Raw) -> Article:
        """Convert GitHub release dict to Article dict.

        Args:
            raw: GitHub release dict with tag_name, name, body, etc.

        Returns:
            Article dict with title, link, guid, pub_date, description, content.
        """
        # title: tag_name or name
        title = raw.get("tag_name") or raw.get("name")

        # link: html_url
        link = raw.get("html_url")

        # guid: tag_name
        guid = raw.get("tag_name")

        # pub_date: published_at
        pub_date = raw.get("published_at")

        # description: body (release notes)
        description = raw.get("body")

        # content: None (no additional content for releases)
        content = None

        return Article(
            title=title,
            link=link,
            guid=guid,
            pub_date=pub_date,
            description=description,
            content=content,
        )

    def tag_parsers(self) -> List[TagParser]:
        """Return tag parsers for this provider.

        Returns:
            Empty list - tag parsers are loaded separately in Plan 02.
        """
        return []

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for an article.

        Args:
            article: Article dict.

        Returns:
            Empty list - chaining is implemented in Plan 02 via chain_tag_parsers.
        """
        return []


# Register this provider - it will be sorted by priority() after all modules load
PROVIDERS.append(GitHubProvider())
