"""GitHub API client for monitoring repository releases.

Provides functions for fetching release information from GitHub REST API
with optional token authentication and rate limit handling.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from src.db import get_connection
from src.models import GitHubRepo, GitHubRelease

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Cache TTL of 1 hour for release data
CACHE_TTL = timedelta(hours=1)


def get_headers() -> dict:
    """Build request headers with optional auth.

    Returns:
        Dict with Accept header and optional Authorization Bearer token.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse owner and repo from GitHub URL.

    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/releases
    - git@github.com:owner/repo.git

    Args:
        url: GitHub repository URL.

    Returns:
        Tuple of (owner, repo).

    Raises:
        ValueError: If URL is not a valid GitHub repo URL.
    """
    import re
    from urllib.parse import urlparse

    # SSH format
    if url.startswith("git@"):
        match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
        if match:
            return match.group(1), match.group(2)

    # HTTPS format
    parsed = urlparse(url)
    if parsed.netloc == "github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")

    raise ValueError(f"Invalid GitHub URL: {url}")


def check_rate_limit(response: httpx.Response) -> dict:
    """Extract rate limit info from response headers.

    Args:
        response: httpx.Response from GitHub API.

    Returns:
        Dict with remaining, reset, limit keys.
    """
    return {
        "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
        "reset": int(response.headers.get("X-RateLimit-Reset", 0)),
        "limit": int(response.headers.get("X-RateLimit-Limit", 60))
    }


def is_rate_limited(response: httpx.Response) -> bool:
    """Check if response indicates rate limit exceeded.

    Args:
        response: httpx.Response from GitHub API.

    Returns:
        True if rate limited (403 with rate limit message).
    """
    if response.status_code == 403:
        return "rate limit" in response.text.lower()
    return False


def get_wait_time(response: httpx.Response) -> int:
    """Get seconds to wait until rate limit resets.

    Args:
        response: httpx.Response from GitHub API.

    Returns:
        Seconds until rate limit reset (0 if already passed).
    """
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
    now = datetime.now(timezone.utc).timestamp()
    return max(0, int(reset_time - now))


def is_cache_fresh(last_fetched: Optional[str]) -> bool:
    """Check if cached data is still fresh.

    Args:
        last_fetched: ISO timestamp string of last fetch.

    Returns:
        True if cache is fresh (within CACHE_TTL).
    """
    if not last_fetched:
        return False
    last = datetime.fromisoformat(last_fetched)
    return datetime.now(timezone.utc) - last < CACHE_TTL


class RateLimitError(Exception):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class GitHubAPIError(Exception):
    """Raised when GitHub API returns an error."""
    pass


def fetch_latest_release(owner: str, repo: str) -> Optional[dict]:
    """Fetch latest release for a repository.

    Args:
        owner: GitHub owner (user or organization).
        repo: Repository name.

    Returns:
        Dict with tag_name, name, body, published_at, html_url, or None if no releases.

    Raises:
        RateLimitError: If rate limit is exceeded.
        GitHubAPIError: If API returns an error.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases/latest"
    response = httpx.get(url, headers=get_headers(), timeout=10.0)

    # Check rate limit first
    rate_info = check_rate_limit(response)
    if rate_info["remaining"] < 10:
        logger.warning(f"GitHub API rate limit low: {rate_info['remaining']} remaining")

    if response.status_code == 404:
        return None  # No releases

    if is_rate_limited(response):
        wait_time = get_wait_time(response)
        raise RateLimitError(f"Rate limited. Retry after {wait_time} seconds")

    if response.status_code == 403:
        raise GitHubAPIError(f"GitHub API error: {response.text}")

    response.raise_for_status()
    return response.json()


def store_release(repo_id: str, release_data: dict) -> GitHubRelease:
    """Store a release in the database.

    Args:
        repo_id: ID of the parent GitHubRepo.
        release_data: Dict from GitHub API with tag_name, name, body, etc.

    Returns:
        Created GitHubRelease object.
    """
    import uuid

    release_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO github_releases (id, repo_id, tag_name, name, body, html_url, published_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_id,
                repo_id,
                release_data.get("tag_name"),
                release_data.get("name"),
                release_data.get("body"),
                release_data.get("html_url"),
                release_data.get("published_at"),
                now,
            ),
        )
        conn.commit()

        # Fetch the stored release (handles INSERT OR IGNORE case)
        cursor.execute(
            "SELECT * FROM github_releases WHERE repo_id = ? AND tag_name = ?",
            (repo_id, release_data.get("tag_name")),
        )
        row = cursor.fetchone()
        if row:
            return GitHubRelease(
                id=row["id"],
                repo_id=row["repo_id"],
                tag_name=row["tag_name"],
                name=row["name"],
                body=row["body"],
                html_url=row["html_url"],
                published_at=row["published_at"],
                created_at=row["created_at"],
            )
        raise GitHubAPIError("Failed to store release")
    finally:
        conn.close()


def get_repo_releases(repo_id: str) -> list[GitHubRelease]:
    """Get all releases for a repository.

    Args:
        repo_id: ID of the GitHubRepo.

    Returns:
        List of GitHubRelease objects ordered by published_at descending.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM github_releases WHERE repo_id = ? ORDER BY published_at DESC",
            (repo_id,),
        )
        rows = cursor.fetchall()
        return [
            GitHubRelease(
                id=row["id"],
                repo_id=row["repo_id"],
                tag_name=row["tag_name"],
                name=row["name"],
                body=row["body"],
                html_url=row["html_url"],
                published_at=row["published_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    finally:
        conn.close()


class RepoNotFoundError(Exception):
    """Raised when a GitHub repo is not found in the database."""
    pass


def get_or_create_github_repo(owner: str, repo: str) -> GitHubRepo:
    """Get existing GitHub repo or create new entry if not exists.

    Args:
        owner: GitHub owner (user or org)
        repo: Repository name

    Returns:
        GitHubRepo object (existing or newly created)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM github_repos WHERE owner = ? AND repo = ?",
            (owner, repo),
        )
        row = cursor.fetchone()
        if row:
            return GitHubRepo(
                id=row["id"],
                name=row["name"],
                owner=row["owner"],
                repo=row["repo"],
                last_fetched=row["last_fetched"],
                last_tag=row["last_tag"],
                created_at=row["created_at"],
            )
    finally:
        conn.close()

    # Create new entry
    repo_id = generate_repo_id()
    name = f"{owner}/{repo}"
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO github_repos (id, name, owner, repo, last_fetched, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (repo_id, name, owner, repo, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return GitHubRepo(
        id=repo_id,
        name=name,
        owner=owner,
        repo=repo,
        last_fetched=now,
        last_tag=None,
        created_at=now,
    )


def generate_repo_id() -> str:
    """Generate a unique ID for a new GitHub repo."""
    return str(uuid.uuid4())


def add_github_repo(url: str) -> GitHubRepo:
    """Add a GitHub repository to monitor.

    Parses the URL to extract owner/repo, validates by fetching from GitHub API.

    Args:
        url: GitHub repository URL.

    Returns:
        Created GitHubRepo object.

    Raises:
        ValueError: If URL is invalid or repo cannot be accessed.
    """
    owner, repo = parse_github_url(url)

    # Verify repo exists by trying to fetch releases
    try:
        release_data = fetch_latest_release(owner, repo)
    except RateLimitError as e:
        # Still add the repo, but note the rate limit issue
        logger.warning(f"Rate limit when verifying repo: {e}")
    except GitHubAPIError as e:
        raise ValueError(f"Cannot access GitHub repository: {e}") from e

    # Check if repo already exists
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM github_repos WHERE owner = ? AND repo = ?",
            (owner, repo),
        )
        existing = cursor.fetchone()
        if existing:
            raise ValueError(f"GitHub repository already added: {owner}/{repo}")
    finally:
        conn.close()

    repo_id = generate_repo_id()
    name = f"{owner}/{repo}"
    now = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO github_repos (id, name, owner, repo, last_fetched, last_tag, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (repo_id, name, owner, repo, now, None, now),
        )
        conn.commit()
    finally:
        conn.close()

    result = GitHubRepo(
        id=repo_id,
        name=name,
        owner=owner,
        repo=repo,
        last_fetched=now,
        last_tag=None,
        created_at=now,
    )

    # If we got a release, store it
    if release_data:
        store_release(repo_id, release_data)
        # Update last_tag
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE github_repos SET last_tag = ? WHERE id = ?",
                (release_data.get("tag_name"), repo_id),
            )
            conn.commit()
        finally:
            conn.close()
        result.last_tag = release_data.get("tag_name")

    return result


def list_github_repos() -> list[GitHubRepo]:
    """List all monitored GitHub repositories.

    Returns:
        List of GitHubRepo objects.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM github_repos ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [
            GitHubRepo(
                id=row["id"],
                name=row["name"],
                owner=row["owner"],
                repo=row["repo"],
                last_fetched=row["last_fetched"],
                last_tag=row["last_tag"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def get_github_repo(repo_id: str) -> Optional[GitHubRepo]:
    """Get a single GitHub repo by ID.

    Args:
        repo_id: The ID of the repo.

    Returns:
        GitHubRepo object or None if not found.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM github_repos WHERE id = ?", (repo_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return GitHubRepo(
            id=row["id"],
            name=row["name"],
            owner=row["owner"],
            repo=row["repo"],
            last_fetched=row["last_fetched"],
            last_tag=row["last_tag"],
            created_at=row["created_at"],
        )
    finally:
        conn.close()


def remove_github_repo(repo_id: str) -> bool:
    """Remove a GitHub repo and its releases.

    Args:
        repo_id: The ID of the repo to remove.

    Returns:
        True if deleted, False if not found.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM github_repos WHERE id = ?", (repo_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def refresh_github_repo(repo_id: str) -> dict:
    """Refresh a GitHub repo to fetch latest release.

    Args:
        repo_id: The ID of the repo to refresh.

    Returns:
        Dict with new_release flag, release info, and any error.

    Raises:
        RepoNotFoundError: If repo does not exist.
    """
    repo = get_github_repo(repo_id)
    if not repo:
        raise RepoNotFoundError(f"GitHub repo not found: {repo_id}")

    # Check cache freshness first
    if is_cache_fresh(repo.last_fetched):
        logger.info(f"Skipping refresh for {repo.name} (cache fresh)")
        return {
            "new_release": False,
            "message": "Cache fresh, skipped API request",
            "release": None,
        }

    try:
        release_data = fetch_latest_release(repo.owner, repo.repo)
    except RateLimitError as e:
        return {
            "new_release": False,
            "error": str(e),
            "message": "Rate limit exceeded. Set GITHUB_TOKEN environment variable for higher limit (5000 req/hour)",
        }
    except GitHubAPIError as e:
        return {
            "new_release": False,
            "error": str(e),
        }

    now = datetime.now(timezone.utc).isoformat()

    if release_data is None:
        # No releases
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE github_repos SET last_fetched = ? WHERE id = ?",
                (now, repo_id),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "new_release": False,
            "message": "No releases found",
            "release": None,
        }

    # Store the release
    release = store_release(repo_id, release_data)

    # Update repo metadata
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE github_repos SET last_fetched = ?, last_tag = ? WHERE id = ?",
            (now, release_data.get("tag_name"), repo_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "new_release": True,
        "release": release,
    }


# Common changelog filenames to try, in order of priority
CHANGELOG_FILENAMES = [
    "CHANGELOG.md",
    "CHANGELOG",
    "HISTORY.md",
    "CHANGES.md",
    "CHANGELOG.rst",
]

# Common branch names to try
GITHUB_BRANCHES = ["main", "master"]


def detect_changelog_file(owner: str, repo: str) -> Optional[tuple[str, str]]:
    """Detect which changelog file exists in a repository.

    Tries common changelog filenames in order of priority, first match wins.
    Tries main branch first, then master.

    Args:
        owner: GitHub owner (user or organization).
        repo: Repository name.

    Returns:
        Tuple of (filename, branch) if found, None if no changelog detected.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    for branch in GITHUB_BRANCHES:
        for filename in CHANGELOG_FILENAMES:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}"
            try:
                response = httpx.head(url, headers=headers, timeout=10.0, follow_redirects=True)
                if response.status_code == 200:
                    return (filename, branch)
            except (httpx.RequestError, OSError):
                continue
    return None


def fetch_changelog_content(owner: str, repo: str, filename: str, branch: str) -> Optional[str]:
    """Fetch changelog content from raw.githubusercontent.com.

    Args:
        owner: GitHub owner (user or organization).
        repo: Repository name.
        filename: Changelog filename (e.g., "CHANGELOG.md").
        branch: Branch name (e.g., "main").

    Returns:
        Raw markdown content as string, or None if fetch fails.
    """
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}"
    headers = {
        "Accept": "text/plain",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    try:
        response = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        if response.status_code == 200:
            return response.text
    except (httpx.RequestError, OSError):
        pass
    return None


def store_changelog_as_article(repo_id: str, repo_name: str, content: str, filename: str, source_url: str) -> str:
    """Store changelog content as an article.

    Creates a new article or updates existing article with same guid.
    The article's guid is prefixed with "changelog:" to distinguish from feed articles.

    Args:
        repo_id: ID of the parent GitHubRepo.
        repo_name: Display name of the repo (e.g., "owner/repo").
        content: Raw changelog markdown content.
        filename: Original filename (e.g., "CHANGELOG.md").
        source_url: URL to the raw changelog file.

    Returns:
        ID of the created or updated article.
    """
    import uuid
    from src.db import get_connection

    now = datetime.now(timezone.utc).isoformat()

    # Create a unique guid for this changelog
    guid = f"changelog:{repo_name}:{filename}"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE guid = ?", (guid,))
        existing = cursor.fetchone()
        if existing:
            # UPDATE existing article - keep same article_id
            article_id = existing["id"]
            cursor.execute(
                """UPDATE articles SET content = ?, link = ?, pub_date = ?
                   WHERE guid = ?""",
                (content, source_url, now, guid),
            )
            # Update FTS5 entry
            cursor.execute(
                """INSERT OR REPLACE INTO articles_fts(rowid, title, description, content)
                   SELECT rowid, title, description, content FROM articles WHERE id = ?""",
                (article_id,),
            )
        else:
            # INSERT new article
            article_id = str(uuid.uuid4())
            cursor.execute(
                """INSERT INTO articles (id, feed_id, repo_id, title, link, guid, pub_date, content, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article_id,
                    "",  # feed_id is empty string for GitHub-sourced content
                    repo_id,
                    f"{repo_name} Changelog",
                    source_url,
                    guid,
                    now,  # Use current time as pub_date
                    content,
                    now,
                ),
            )
            # Sync changelog to FTS5 for search
            cursor.execute(
                """INSERT INTO articles_fts(rowid, title, description, content)
                   SELECT rowid, title, NULL as description, content FROM articles WHERE id = ?""",
                (article_id,),
            )

        conn.commit()
        return article_id
    finally:
        conn.close()


def get_repo_changelog(repo_id: str) -> Optional[dict]:
    """Get stored changelog article for a repository.

    Args:
        repo_id: ID of the GitHubRepo.

    Returns:
        Dict with article info if changelog exists, None otherwise.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, link, content, created_at
            FROM articles
            WHERE repo_id = ? AND guid LIKE 'changelog:%'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (repo_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "title": row["title"],
                "link": row["link"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
        return None
    finally:
        conn.close()


def refresh_changelog(repo_id: str) -> dict:
    """Refresh changelog for a GitHub repo: detect, fetch, and store.

    Args:
        repo_id: ID of the GitHub repo to refresh changelog for.

    Returns:
        Dict with changelog_found flag, article_id, filename, and any error.
    """
    repo = get_github_repo(repo_id)
    if not repo:
        raise RepoNotFoundError(f"GitHub repo not found: {repo_id}")

    # Detect changelog file
    changelog_info = detect_changelog_file(repo.owner, repo.repo)
    if not changelog_info:
        return {
            "changelog_found": False,
            "message": f"No changelog file detected (tried: {', '.join(CHANGELOG_FILENAMES)})",
            "article_id": None,
        }

    filename, branch = changelog_info

    # Fetch content
    content = fetch_changelog_content(repo.owner, repo.repo, filename, branch)
    if not content:
        return {
            "changelog_found": True,
            "filename": filename,
            "error": "Failed to fetch changelog content",
            "article_id": None,
        }

    # Build source URL
    source_url = f"https://raw.githubusercontent.com/{repo.owner}/{repo.repo}/{branch}/{filename}"

    # Store as article
    article_id = store_changelog_as_article(repo_id, repo.name, content, filename, source_url)

    return {
        "changelog_found": True,
        "filename": filename,
        "branch": branch,
        "article_id": article_id,
        "message": f"Changelog ({filename}) updated",
    }