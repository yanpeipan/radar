"""Web crawling operations for RSS reader.

Provides functions for crawling arbitrary URLs and extracting article content
using Readability algorithm. Handles rate limiting, robots.txt compliance (lazy mode),
and article storage in the existing articles table.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx
from github import RateLimitExceededException, GithubException
from src.application.config import get_timezone
from bs4 import BeautifulSoup
from readability import Document
from robotexclusionrulesparser import RobotExclusionRulesParser

from src.storage.sqlite import get_db
from src.models import Article

logger = logging.getLogger(__name__)

# Browser-like User-Agent header to avoid 403 bot blocks
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Rate limiting state: {host: last_request_timestamp}
_rate_limit_state: dict[str, float] = {}

# GitHub URL pattern for blob pages: github.com/{owner}/{repo}/blob/{branch}/{path}
GITHUB_BLOB_PATTERN = re.compile(r'^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$')

# GitHub URL pattern for commits pages: github.com/{owner}/{repo}/commits/{branch}[/{path}]
GITHUB_COMMITS_PATTERN = re.compile(r'^https://github\.com/([^/]+)/([^/]+)/commits/([^/]+)(?:/(.+))?$')


def is_github_blob_url(url: str) -> Optional[tuple[str, str, str, str]]:
    """Detect if URL is a GitHub blob URL.

    Args:
        url: URL to check

    Returns:
        Tuple of (owner, repo, branch, path) if match, None otherwise.
        Per D-GH01: Detect GitHub URL type BEFORE fetching.
    """
    match = GITHUB_BLOB_PATTERN.match(url)
    if match:
        return match.group(1), match.group(2), match.group(3), match.group(4)
    return None


def is_github_commits_url(url: str) -> Optional[tuple[str, str, str, Optional[str]]]:
    """Detect if URL is a GitHub commits URL.

    Args:
        url: URL to check

    Returns:
        Tuple of (owner, repo, branch, path_or_none) if match, None otherwise.
        Per D-GH01: Detect GitHub URL type BEFORE fetching.
        Note: path is Optional because /commits can be just /commits/{branch} without a file path.
    """
    match = GITHUB_COMMITS_PATTERN.match(url)
    if match:
        return match.group(1), match.group(2), match.group(3), match.group(4)
    return None


def fetch_github_file_metadata(owner: str, repo: str, path: str) -> tuple[Optional[str], Optional[str]]:
    """Fetch file metadata via GitHub Contents API.

    Args:
        owner: GitHub owner (user or org)
        repo: Repository name
        path: File path within the repository

    Returns:
        Tuple of (title, error_message).
        title is formatted as "{owner}/{repo} / {H1}" or "{owner}/{repo} / {filename}".
        error_message is None on success.
        Per D-GH02: Use GitHub Contents API for blob URLs.
        Per D-GH03: Title format with H1 extraction.
    """
    try:
        client = _get_github_client()
        gh_repo = client.get_repo(f"{owner}/{repo}")
        contents = gh_repo.get_contents(path)
        # contents is a ContentObject with content (base64), name, path, etc.

        # Extract filename from path for fallback title
        filename = path.split('/')[-1] if '/' in path else path

        # Decode base64 content and extract H1
        if contents.content:
            content_bytes = base64.b64decode(contents.content)
            content = content_bytes.decode('utf-8')

            # Extract first H1 from markdown: lines starting with "# " (not "## " etc)
            h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            if h1_match:
                h1_text = h1_match.group(1).strip()
                title = f"{owner}/{repo} / {h1_text}"
            else:
                # No H1 found, use filename
                title = f"{owner}/{repo} / {filename}"
            return title, None
        return None, "No content field in API response"
    except RateLimitExceededException as e:
        logger.warning("GitHub Contents API rate limited for %s/%s", owner, repo)
        return None, "Rate limited"
    except GithubException as e:
        logger.warning("Failed to fetch GitHub metadata for %s/%s: %s", owner, repo, e)
        return None, str(e)


def fetch_github_commit_time(owner: str, repo: str, path: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Fetch latest commit time via GitHub Commits API.

    Args:
        owner: GitHub owner (user or org)
        repo: Repository name
        path: Optional file path to get commit time for specific file.
              If None, returns latest commit for the branch.

    Returns:
        Tuple of (iso_timestamp, error_message).
        iso_timestamp is in ISO 8601 format from GitHub API.
        error_message is None on success.
        Per D-GH04: Use GitHub Commits API for pub_date on commits URLs.
    """
    try:
        client = _get_github_client()
        gh_repo = client.get_repo(f"{owner}/{repo}")
        commits = gh_repo.get_commits(path=path if path else None)
        # commits is a PaginatedList
        first_commit = commits[0]
        timestamp = first_commit.commit.author.date.isoformat()
        return timestamp, None
    except RateLimitExceededException as e:
        logger.warning("GitHub Commits API rate limited for %s/%s", owner, repo)
        return None, "Rate limited"
    except GithubException as e:
        logger.warning("Failed to fetch commit time for %s/%s: %s", owner, repo, e)
        return None, str(e)


def _convert_github_blob_to_raw(url: str) -> str:
    """Convert GitHub blob URLs to raw content URLs.

    GitHub blob pages (github.com/user/repo/blob/branch/path) are JavaScript-rendered
    and return minimal HTML when fetched statically. Raw URLs (raw.githubusercontent.com)
    return the actual file content directly.

    Args:
        url: URL to convert

    Returns:
        Raw URL if input was a GitHub blob URL, otherwise unchanged URL
    """
    # Pattern: https://github.com/{user}/{repo}/blob/{branch}/{path}
    pattern = r'^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$'
    match = re.match(pattern, url)
    if match:
        user, repo, branch, path = match.groups()
        return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"
    return url


def ensure_crawled_feed() -> None:
    """Create 'crawled' system feed if it doesn't exist.

    Creates feed with id='crawled', name='Crawled Pages', url=''.
    This is the system feed for storing crawled web pages.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM feeds WHERE id = 'crawled'")
        if cursor.fetchone() is None:
            now = datetime.now(get_timezone()).isoformat()
            cursor.execute(
                """INSERT INTO feeds (id, name, url, created_at)
                   VALUES ('crawled', 'Crawled Pages', '', ?)""",
                (now,)
            )
            conn.commit()


def crawl_url(url: str, ignore_robots: bool = False) -> Optional[dict]:
    """Fetch and extract article content from a URL.

    Args:
        url: URL to crawl
        ignore_robots: If True, skip robots.txt check (lazy mode)

    Returns:
        Dict with title, link, content, or None on failure

    Raises:
        Logs warnings for robots.txt failures (continues in lazy mode)
        Logs errors and returns None for fetch/extraction failures
    """
    parsed = urlparse(url)
    host = parsed.netloc

    # D-03: Rate limiting - 2-second delay between requests to same host
    if host in _rate_limit_state:
        elapsed = time.time() - _rate_limit_state[host]
        if elapsed < 2.0:
            time.sleep(2.0 - elapsed)
    _rate_limit_state[host] = time.time()

    # D-GH01: Detect GitHub URL type BEFORE fetching
    github_blob = is_github_blob_url(url)
    github_commits = is_github_commits_url(url) if not github_blob else None

    # Track GitHub-specific pub_date and title if available
    github_pub_date = None
    github_title = None

    # D-02: robots.txt check (unless ignore_robots flag set)
    # For GitHub blob URLs, check robots.txt for raw.githubusercontent.com
    robots_check_url = _convert_github_blob_to_raw(url)
    robots_parsed = urlparse(robots_check_url)

    # Skip robots.txt check for raw.githubusercontent.com - it's a static file CDN
    # where robots.txt is not critical for legitimate crawling
    skip_robots_check = robots_parsed.netloc == "raw.githubusercontent.com"

    if not ignore_robots and not skip_robots_check:
        robots_url = f"{robots_parsed.scheme}://{robots_parsed.netloc}/robots.txt"
        try:
            parser = RobotExclusionRulesParser()
            response = httpx.get(robots_url, headers=BROWSER_HEADERS, timeout=10.0)
            parser.parse(response.text)
            if not parser.is_allowed(robots_check_url, "*"):
                logger.warning("Blocked by robots.txt: %s", robots_check_url)
                return None
        except Exception as e:
            # D-05: Lazy mode - log warning but continue on robots.txt errors
            logger.warning("Failed to fetch robots.txt for %s: %s", robots_parsed.netloc, e)

    # D-GH01, D-GH02, D-GH03: GitHub blob URL - fetch metadata first
    if github_blob:
        owner, repo, branch, path = github_blob
        github_title, gh_error = fetch_github_file_metadata(owner, repo, path)
        if gh_error:
            logger.warning("GitHub metadata fetch failed for %s: %s", url, gh_error)
            # Fall back to raw fetch - will use Readability title

        # Also get commit time for pub_date
        github_pub_date, _ = fetch_github_commit_time(owner, repo, path)

    # D-GH01, D-GH04: GitHub commits URL - get commit time for pub_date
    if github_commits and not github_blob:
        owner, repo, branch, path = github_commits
        github_pub_date, _ = fetch_github_commit_time(owner, repo, path)
        if github_pub_date:
            logger.info("Using commit time as pub_date for %s: %s", url, github_pub_date)

    # Fetch page content with httpx
    # For GitHub blob URLs, use the raw URL to get actual content
    try:
        response = httpx.get(robots_check_url, headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError, httpx.TimeoutException, OSError) as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None

    # D-01 + D-04: Extract content with Readability
    try:
        doc = Document(response.text)
        title = github_title if github_title else doc.title()
        # summary() returns HTML; strip tags for plain text content
        soup = BeautifulSoup(doc.summary(), 'html.parser')
        content = soup.get_text(separator='\n', strip=True)

        # D-05: Handle empty extraction
        if not content or len(content) < 100:
            logger.warning("Extracted content too short from %s", url)
            return None

    except Exception as e:
        logger.error("Failed to extract content from %s: %s", url, e)
        return None

    # D-07: Store article using unified store_article function
    # Ensure system feed exists
    ensure_crawled_feed()

    # Use URL as guid for deduplication
    guid = url
    pub_date = github_pub_date if github_pub_date else datetime.now(get_timezone()).isoformat()

    # Use unified store_article function (handles INSERT or UPDATE by guid, FTS5 sync)
    from src.storage.sqlite import store_article
    article_id = store_article(
        guid=guid,
        title=title or "No title",
        content=content,
        link=url,
        feed_id="crawled",
        repo_id=None,
        pub_date=pub_date,
    )

    return {
        'title': title or "No title",
        'link': url,
        'content': content,
        'pub_date': pub_date,
    }
