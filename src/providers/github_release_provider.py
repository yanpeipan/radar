"""GitHub release provider for monitoring repository releases.

Handles GitHub repository URLs and fetches the latest release.
Priority is 200 (higher than GitHubProvider's 100 - tried first for releases).

This provider focuses specifically on release data, allowing the general
GitHubProvider to handle non-release repository URLs.
"""
from __future__ import annotations

import logging
import os
from typing import List
from urllib.parse import urlparse

from github import Github, RateLimitExceededException, GithubException

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, Raw, TagParser
from src.tags import chain_tag_parsers

logger = logging.getLogger(__name__)

# Reuse the singleton from utils/github.py
from src.utils.github import _get_github_client


class GitHubReleaseProvider:
    """Content provider for GitHub repository releases.

    Detects github.com URLs and fetches the latest release
    using the GitHub API. Higher priority (200) than GitHubProvider (100).
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
            200 - higher than GitHubProvider (100), tried first for releases.
        """
        return 200

    def crawl(self, url: str) -> List[Raw]:
        """Fetch latest GitHub release for a repository.

        Args:
            url: GitHub repository URL.

        Returns:
            List with single release dict, or empty list if no release or error.
        """
        from src.utils.github import parse_github_url

        try:
            owner, repo = parse_github_url(url)
            client = _get_github_client()
            gh_repo = client.get_repo(f"{owner}/{repo}")
            release = gh_repo.get_latest_release()

            release_data = {
                "tag_name": release.tag_name,
                "name": release.name,
                "body": release.body,
                "html_url": release.html_url,
                "published_at": release.published_at.isoformat() if release.published_at else None,
            }
            logger.debug("GitHubReleaseProvider.crawl(%s) returned release: %s", url, release_data.get("tag_name"))
            return [release_data]
        except RateLimitExceededException as e:
            logger.error("GitHub API rate limited for %s: %s", url, e)
            return []
        except GithubException as e:
            logger.error("GitHub API error for %s: %s", url, e)
            return []
        except ValueError as e:
            logger.error("Invalid GitHub URL %s: %s", url, e)
            return []
        except Exception as e:
            logger.error("GitHubReleaseProvider.crawl(%s) failed: %s", url, e)
            return []

    async def crawl_async(self, url: str) -> List[Raw]:
        """Asynchronous crawl using thread pool executor.

        Since GitHub API calls via PyGithub are synchronous, this method
        runs crawl() in a thread pool to avoid blocking the event loop.

        Args:
            url: GitHub repository URL.

        Returns:
            List of release dicts from crawl().
        """
        import asyncio
        return await asyncio.to_thread(self.crawl, url)

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
            List with ReleaseTagParser instance for release-specific tagging.
        """
        from src.tags.release_tag_parser import ReleaseTagParser
        return [ReleaseTagParser()]

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for an article using all loaded tag parsers.

        Args:
            article: Article dict with title, description, etc.

        Returns:
            List of tag names from all tag parsers (union, deduped).
        """
        return chain_tag_parsers(article)

    def feed_meta(self, url: str) -> "Feed":
        """Fetch repository metadata from GitHub.

        Args:
            url: GitHub repository URL.

        Returns:
            Feed object with name and url populated.
        """
        from src.utils.github import parse_github_url
        from src.models import Feed
        from src.application.config import get_timezone
        from datetime import datetime

        owner, repo = parse_github_url(url)
        client = _get_github_client()
        gh_repo = client.get_repo(f"{owner}/{repo}")

        repo_name = gh_repo.full_name or f"{owner}/{repo}"
        now = datetime.now(get_timezone()).isoformat()

        return Feed(
            id="",  # ID not assigned - this is metadata only
            name=repo_name,
            url=url,
            etag=None,
            last_modified=None,
            last_fetched=now,
            created_at=now,
        )


# Register this provider - higher priority (200) than GitHubProvider (100)
PROVIDERS.append(GitHubReleaseProvider())
