# Phase 4: GitHub API Client + Releases Integration - Research

**Researched:** 2026-03-23
**Domain:** GitHub REST API for releases monitoring
**Confidence:** HIGH (based on official GitHub API documentation)

## Summary

Phase 4 implements GitHub repository monitoring using the GitHub REST API. Users can add GitHub repository URLs and the system will fetch release information (tag_name, body, published_at, html_url). The implementation uses httpx (already in dependencies) for API calls, supports optional GitHub token authentication via `GITHUB_TOKEN` environment variable, and handles rate limits gracefully.

Key decisions locked from STATE.md:
- GitHub Releases using GitHub API (not third-party library)
- GitHub Changelog using Scrapling (deferred to Phase 5)

**Primary recommendation:** Use httpx directly with GitHub REST API v3, parse owner/repo from URL, implement conditional fetching with caching, and handle rate limits via token auth and response headers.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GH-01 | User can add a GitHub repository URL to monitor | URL parsing patterns documented below |
| GH-02 | System fetches release information using GitHub API (tag_name, body, published_at, html_url) | GitHub API endpoint documented below |
| GH-03 | System supports GitHub token authentication via environment variable (GITHUB_TOKEN) | Auth pattern documented below |
| GH-04 | System handles GitHub API rate limits gracefully (60 req/hour unauthenticated, 5000 req/hour with token) | Rate limit handling documented below |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.x | HTTP client | Already in dependencies. GitHub REST API is simple REST/JSON, no SDK needed. |

### No New Dependencies for Phase 4
Phase 4 covers GitHub API client only. No new packages required. changelog scraping (Phase 5) will add scrapling.

**Installation:** None (httpx already installed)

## Architecture Patterns

### Recommended Project Structure
```
src/
├── __init__.py
├── cli.py          # Existing CLI (add repo commands)
├── db.py           # Existing DB (add github_repos table)
├── feeds.py        # Existing feed logic
├── github.py       # NEW: GitHub API client module
├── models.py       # Add GitHubRepo model
└── ...
```

### Pattern 1: GitHub API Client Module (github.py)
**What:** Dedicated module for GitHub API interactions
**When to use:** All GitHub API calls go through this module
**Example:**
```python
import httpx
import os
from typing import Optional

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

def get_headers() -> dict:
    """Build request headers with optional auth."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

def fetch_latest_release(owner: str, repo: str) -> Optional[dict]:
    """Fetch latest release for a repository."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases/latest"
    response = httpx.get(url, headers=get_headers(), timeout=10.0)

    if response.status_code == 404:
        return None  # No releases
    response.raise_for_status()

    return response.json()
    # Fields: tag_name, name, body, published_at, html_url, author, assets
```

### Pattern 2: URL Parsing for GitHub Repos
**What:** Extract owner/repo from various GitHub URL formats
**When to use:** When user adds a repo via URL
**Example:**
```python
import re
from urllib.parse import urlparse

def parse_github_url(url: str) -> tuple[str, str]:
    """Parse owner and repo from GitHub URL.

    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/releases
    - git@github.com:owner/repo.git

    Returns:
        Tuple of (owner, repo)

    Raises:
        ValueError: If URL is not a valid GitHub repo URL
    """
    # SSH format
    if url.startswith("git@"):
        match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
        if match:
            return match.group(1), match.group(2).replace(".git", "")

    # HTTPS format
    parsed = urlparse(url)
    if parsed.netloc == "github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")

    raise ValueError(f"Invalid GitHub URL: {url}")
```

### Pattern 3: Rate Limit Aware Fetching
**What:** Check rate limit headers before making requests
**When to use:** Before every GitHub API request
**Example:**
```python
from datetime import datetime, timezone

def check_rate_limit(response: httpx.Response) -> dict:
    """Extract rate limit info from response headers."""
    return {
        "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
        "reset": int(response.headers.get("X-RateLimit-Reset", 0)),
        "limit": int(response.headers.get("X-RateLimit-Limit", 60))
    }

def is_rate_limited(response: httpx.Response) -> bool:
    """Check if response indicates rate limit exceeded."""
    if response.status_code == 403:
        return "rate limit" in response.text.lower()
    return False

def get_wait_time(response: httpx.Response) -> int:
    """Get seconds to wait until rate limit resets."""
    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
    now = datetime.now(timezone.utc).timestamp()
    return max(0, reset_time - now)
```

### Pattern 4: Caching for Rate Limit Protection
**What:** Cache API responses to avoid redundant requests
**When to use:** Before fetching, check if cached data is fresh
**Example:**
```python
from datetime import datetime, timezone, timedelta

# Cache TTL of 1 hour for release data
CACHE_TTL = timedelta(hours=1)

def is_cache_fresh(last_fetched: Optional[str]) -> bool:
    """Check if cached data is still fresh."""
    if not last_fetched:
        return False
    last = datetime.fromisoformat(last_fetched)
    return datetime.now(timezone.utc) - last < CACHE_TTL
```

### Pattern 5: GitHubRepo Model
**What:** Dataclass for GitHub repository monitoring
**When to use:** When storing repo in database
**Example:**
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class GitHubRepo:
    """Represents a monitored GitHub repository.

    Attributes:
        id: Unique identifier for the repo entry.
        name: Display name (derived from repo name).
        owner: GitHub owner (user or organization).
        repo: Repository name.
        last_fetched: ISO timestamp of last API check.
        last_tag: Last seen release tag (for change detection).
        created_at: ISO timestamp when repo was added.
    """
    id: str
    name: str
    owner: str
    repo: str
    created_at: str
    last_fetched: Optional[str] = None
    last_tag: Optional[str] = None
```

### Database Schema Extension
```sql
-- github_repos table: stores monitored GitHub repositories
CREATE TABLE IF NOT EXISTS github_repos (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner TEXT NOT NULL,
    repo TEXT NOT NULL,
    last_fetched TEXT,
    last_tag TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(owner, repo)
);

-- github_releases table: stores release information
CREATE TABLE IF NOT EXISTS github_releases (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES github_repos(id) ON DELETE CASCADE,
    tag_name TEXT NOT NULL,
    name TEXT,
    body TEXT,
    html_url TEXT NOT NULL,
    published_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo_id, tag_name)
);

CREATE INDEX IF NOT EXISTS idx_github_releases_repo_id ON github_releases(repo_id);
CREATE INDEX IF NOT EXISTS idx_github_releases_published ON github_releases(published_at);
```

### CLI Command Structure
```
repo add <github-url>   # Add a GitHub repo to monitor
repo list              # List all monitored repos
repo remove <id>       # Remove a repo
repo refresh [id]       # Refresh releases (single or all)
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub API client | PyGithub or github3.py | httpx directly | Simple REST/JSON, no SDK overhead, already have httpx |
| URL parsing | Custom regex for all cases |urllib.parse + minimal regex | Standard library handles HTTPS URLs |
| Rate limit tracking | Build custom rate limiter | Use response headers | GitHub API provides headers natively |
| Release storage | Store only latest | Store in releases table | Need history for change detection |

## Common Pitfalls

### Pitfall: GitHub API Unauthenticated Rate Limit Exhaustion
**What goes wrong:** With 60 req/hour limit, monitoring even 5 repos exhausts limit quickly.

**How to avoid:**
1. Always use `GITHUB_TOKEN` env var for auth (5,000 req/hour)
2. Implement 1-hour cache TTL to avoid redundant fetches
3. Check `X-RateLimit-Remaining` header before requests
4. When limit is low, show warning to user

**Implementation approach:**
```python
# In github.py module
def fetch_with_rate_limit_handling(owner: str, repo: str) -> Optional[dict]:
    """Fetch with automatic rate limit handling."""
    if is_rate_limited_by_cache():
        raise RateLimitError("Cached data still fresh, skipping request")

    try:
        response = httpx.get(url, headers=get_headers(), timeout=10.0)

        rate_info = check_rate_limit(response)

        if rate_info["remaining"] < 10:
            logger.warning(f"GitHub API rate limit low: {rate_info['remaining']} remaining")

        if is_rate_limited(response):
            wait_time = get_wait_time(response)
            logger.warning(f"Rate limited. Wait {wait_time} seconds")
            raise RateLimitError(f"Rate limited, retry after {wait_time}s")

        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
```

### Pitfall: Incorrect URL Parsing
**What goes wrong:** User provides various GitHub URL formats, parsing fails silently.

**How to avoid:**
1. Test with all common formats before implementation
2. Provide clear error messages for invalid URLs
3. Handle both HTTPS and SSH formats

**Test cases:**
- `https://github.com/owner/repo` - should work
- `https://github.com/owner/repo.git` - should strip .git
- `https://github.com/owner/repo/releases` - should extract owner/repo
- `git@github.com:owner/repo.git` - should handle SSH

### Pitfall: Not Handling "No Releases" Case
**What goes wrong:** Some repos have no releases, API returns 404.

**How to avoid:**
- Handle 404 as "no releases" not "error"
- Store this state so refresh doesn't repeatedly hit API

## Code Examples

### GitHub API Request with Optional Auth
```python
# Source: Official GitHub REST API documentation
import httpx
import os

headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

token = os.environ.get("GITHUB_TOKEN")
if token:
    headers["Authorization"] = f"Bearer {token}"

# Get latest release
response = httpx.get(
    "https://api.github.com/repos/owner/repo/releases/latest",
    headers=headers
)
```

### GitHub API Response Fields
```python
# Latest release response fields:
release = {
    "tag_name": "v1.2.3",        # Version tag
    "name": "Version 1.2.3",      # Release title (often same as tag)
    "body": "## Changes\n- Foo", # Markdown release notes
    "published_at": "2024-01-15T10:30:00Z",  # ISO 8601 timestamp
    "html_url": "https://github.com/owner/repo/releases/tag/v1.2.3",
    "author": {                   # Author info
        "login": "username",
        "html_url": "https://github.com/username"
    },
    "assets": []                  # Downloadable assets
}
```

### Check Rate Limit Status
```python
# Source: GitHub REST API rate limit documentation
# Accessing /rate_limit does NOT count against your limit

response = httpx.get(
    "https://api.github.com/rate_limit",
    headers={"Accept": "application/vnd.github+json"}
)
rate_data = response.json()

# Example response:
# {
#   "resources": {
#     "core": {
#       "limit": 5000,
#       "remaining": 4999,
#       "reset": 1372700873,
#       "used": 1
#     }
#   }
# }
```

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx | GitHub API client | Yes | 0.28.1 | N/A |
| GITHUB_TOKEN | Auth for production use | User-provided | N/A | Unauthenticated (60 req/hr) |

**Missing dependencies with fallback:**
- None

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing in project) |
| Config file | pytest.ini or pyproject.toml |
| Quick run command | `pytest tests/test_github.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| GH-01 | URL parsing extracts owner/repo correctly | unit | `pytest tests/test_github.py::test_parse_github_url -x` | No (Wave 0) |
| GH-02 | API fetches release with correct fields | unit | `pytest tests/test_github.py::test_fetch_latest_release -x` | No (Wave 0) |
| GH-03 | Token auth via GITHUB_TOKEN env var | unit | `pytest tests/test_github.py::test_token_auth -x` | No (Wave 0) |
| GH-04 | Rate limit handled gracefully | unit | `pytest tests/test_github.py::test_rate_limit_handling -x` | No (Wave 0) |

### Sampling Rate
- **Per task commit:** `pytest tests/test_github.py -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_github.py` - covers GH-01, GH-02, GH-03, GH-04
- [ ] `tests/conftest.py` - shared fixtures (if needed)
- [ ] Framework install: already in pyproject.toml

## Sources

### Primary (HIGH confidence)
- [GitHub REST API - Releases](https://docs.github.com/en/rest/repos/releases) - Official endpoint documentation
- [GitHub REST API - Rate Limits](https://docs.github.com/en/rest/overview/rate-limits-for-the-rest-api) - Official rate limit numbers (60/hr unauthenticated, 5000/hr authenticated)
- [httpx Documentation](https://www.python-httpx.org/) - HTTP client (already in project)

### Secondary (MEDIUM confidence)
- Existing codebase patterns in `src/feeds.py` and `src/models.py` - Project conventions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - httpx already in project, no new dependencies
- Architecture: HIGH - Follows existing patterns, URL parsing is well-documented
- Pitfalls: HIGH - GitHub API pitfalls well-documented in PITFALLS.md

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (GitHub API changes infrequently)
