# Phase 8: GitHub URL Metadata - Research

**Researched:** 2026-03-23
**Domain:** GitHub API integration for URL metadata extraction
**Confidence:** HIGH

## Summary

Phase 8 improves metadata extraction for crawled GitHub URLs by leveraging GitHub APIs instead of relying solely on raw content parsing. The GitHub Contents API returns base64-encoded file content that must be decoded and parsed for H1 headings, while the GitHub Commits API supports path-based filtering to get the latest commit timestamp for a specific file. Rate limiting (60 req/hour unauthenticated) requires graceful fallback handling.

**Primary recommendation:** Implement URL detection first to route to appropriate strategy, use Contents API for H1 extraction on blob URLs, Commits API with path filter for commit timestamps on commits URLs, and fall back to raw parsing on API failure.

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-GH01:** Detect GitHub URL type BEFORE fetching using URL pattern matching (blob vs commits)
- **D-GH02:** For GitHub blob URLs, use GitHub Contents API (`/repos/{owner}/{repo}/contents/{path}`)
- **D-GH03:** Title format: `{owner}/{repo} / {first H1 in file}` or `{owner}/{repo} / {filename}` if no H1
- **D-GH04:** For GitHub commits URLs, use latest commit time as `pub_date` via Commits API
- **D-GH05:** Graceful fallback on GitHub API failure (rate limit, network error)
- **D-GH06:** GitHub-specific URL handling in `src/crawl.py` with helper functions

### Claude's Discretion
- Implementation approach for URL detection functions
- Exact regex patterns (within the specified URL types)
- Fallback timing and logging details

### Deferred Ideas (OUT OF SCOPE)
- GitHub API rate limit handling with GITHUB_TOKEN support (60 req/hour unauthenticated)
- Playwright rendering for GitHub blob pages
- GitHub PR/issues page support

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GH-01 | Detect GitHub blob vs commits URL before fetching | Verified regex patterns work correctly |
| GH-02 | Use Contents API for file metadata on blob URLs | API returns base64 content - need decode + H1 parse |
| GH-03 | Title format `{owner}/{repo} / {H1}` with fallback | Regex `r'^#\s+(.+)$'` with MULTILINE extracts first H1 |
| GH-04 | Use Commits API for commit timestamp on commits URLs | API supports `path` param, returns `commit.author.date` |
| GH-05 | Graceful fallback on API failure | Rate limit is 60/hour unauth; existing code handles 403 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.27.x | HTTP client | Already in use; supports headers for GitHub API |
| re (built-in) | — | Regex for URL detection and H1 parsing | No external dependency needed |

### Existing Project Patterns
| Module | Purpose | Relevant Patterns |
|--------|---------|-------------------|
| `src/github.py` | GitHub API client | `get_headers()`, `RateLimitError`, `is_rate_limited()` |
| `src/crawl.py` | Web crawling | `_convert_github_blob_to_raw()`, rate limiting state |
| `src/db.py` | Database | `pub_date` column already exists in articles table |
| `src/feeds.py` | Feed handling | `pub_date` handling via `entry.get("published")` |

**No new dependencies required.**

## Architecture Patterns

### URL Detection Pattern
```python
# Blob URL: github.com/{owner}/{repo}/blob/{branch}/{path}
BLOB_PATTERN = re.compile(r'^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$')

# Commits URL: github.com/{owner}/{repo}/commits/{branch}/{path}
COMMITS_PATTERN = re.compile(r'^https://github\.com/([^/]+)/([^/]+)/commits/([^/]+)(?:/(.+))?$')
```

**Verified:** Both patterns correctly extract components (tested with Python).

### GitHub Contents API Response
```
Endpoint: GET /repos/{owner}/{repo}/contents/{path}
Response fields: name, path, sha, size, url, html_url, git_url, download_url,
                  type, content (base64), encoding, _links
```

**Key insight:** The `content` field is base64-encoded raw file content (markdown), NOT HTML. Must decode and parse for H1.

### GitHub Commits API with Path Filter
```
Endpoint: GET /repos/{owner}/{repo}/commits?path={file_path}&per_page=1
Response: Array of commits, most recent first
Timestamp field: [0]['commit']['author']['date']  (ISO 8601 format)
```

**Verified:** API call with `path=README.md&per_page=1` returns latest commit affecting that file.

### Markdown H1 Extraction
```python
import re

def extract_h1(content: str) -> str | None:
    """Extract first H1 heading from markdown content."""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return match.group(1) if match else None
```

**Verified:** Regex correctly extracts first `# heading` line (tested with Python).

### GitHub API Headers (from `src/github.py`)
```python
def get_headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers
```

### Fallback Strategy
1. **Try GitHub API first** (Contents API for H1, Commits API for timestamp)
2. **On rate limit (403 with "rate limit" text) or network error:**
   - For title: use `{owner}/{repo} / {filename}` as fallback
   - For pub_date: use current time
   - Log warning with specific failure reason

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub URL parsing | Custom regex from scratch | Extend existing `_convert_github_blob_to_raw()` pattern | Already has correct URL extraction |
| Base64 decoding | Write custom decoder | `base64.b64decode()` (built-in) | Standard library is sufficient |
| H1 extraction from markdown | HTML parser | Simple regex `r'^#\s+(.+)$'` | Markdown headings are text, not HTML |
| Rate limit detection | Check status code only | Use `is_rate_limited()` from `src/github.py` | Handles 403 + "rate limit" text combo |

## Common Pitfalls

### Pitfall 1: Ignoring Rate Limits
**What goes wrong:** API calls fail after 60 requests in an hour, causing metadata extraction to fail silently.
**Why it happens:** Unauthenticated GitHub API has 60 req/hour limit.
**How to avoid:** Use existing `RateLimitError` handling from `src/github.py`. Check `X-RateLimit-Remaining` header before making API calls. Fall back gracefully.
**Warning signs:** `403` responses with "rate limit exceeded" in body.

### Pitfall 2: Confusing Contents API with HTML Fetching
**What goes wrong:** Trying to parse HTML/H1 from GitHub blob page content.
**Why it happens:** GitHub blob pages are JavaScript-rendered; Contents API returns raw file content, not rendered HTML.
**How to avoid:** Use Contents API for file metadata, not blob page scraping. The `download_url` from Contents API points to raw content.
**Warning signs:** Extracted content looks like raw markdown, not HTML with `<h1>` tags.

### Pitfall 3: URL Pattern Not Catching All Variants
**What goes wrong:** Some GitHub URLs slip through detection (e.g., `/commits` without path).
**Why it happens:** Regex only captures URLs with explicit path after `/commits/`.
**How to avoid:** Make path optional in commits pattern: `(?:/(.+))?$` — verified working.
**Warning signs:** URLs that should be GitHub commits URLs being treated as generic URLs.

## Code Examples

### GitHub API Call Patterns (from `src/github.py`)

```python
import httpx
from src.github import get_headers, is_rate_limited, RateLimitError

def fetch_github_file_content(owner: str, repo: str, path: str) -> tuple[str | None, str | None]:
    """Fetch file content via GitHub Contents API. Returns (content, error)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    try:
        response = httpx.get(url, headers=get_headers(), timeout=10.0)
        if is_rate_limited(response):
            return None, "Rate limited"
        response.raise_for_status()
        data = response.json()
        if 'content' in data:
            import base64
            return base64.b64decode(data['content']).decode('utf-8'), None
        return None, "No content field"
    except (httpx.RequestError, httpx.HTTPError) as e:
        return None, str(e)
```

### GitHub Commits API Call

```python
def fetch_latest_commit_time(owner: str, repo: str, path: str) -> tuple[str | None, str | None]:
    """Fetch latest commit time for a file via GitHub Commits API. Returns (iso_timestamp, error)."""
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"path": path, "per_page": 1}
    try:
        response = httpx.get(url, headers=get_headers(), params=params, timeout=10.0)
        if is_rate_limited(response):
            return None, "Rate limited"
        response.raise_for_status()
        commits = response.json()
        if commits:
            return commits[0]['commit']['author']['date'], None
        return None, "No commits found"
    except (httpx.RequestError, httpx.HTTPError) as e:
        return None, str(e)
```

### pub_date Usage (from `src/db.py` and `src/feeds.py`)

The `pub_date` column in `articles` table stores ISO 8601 timestamp strings:
```python
# From db.py schema
pub_date TEXT,  # ISO 8601 format: "2026-03-23T10:30:00+00:00"

# From feeds.py - how pub_date is populated
pub_date = entry.get("published") or entry.get("updated")
```

The `crawl_url()` function in `src/crawl.py` currently uses `datetime.now(timezone.utc).isoformat()` as pub_date:
```python
now = datetime.now(timezone.utc).isoformat()
# ... stores now as pub_date
```

**For this phase:** Update `crawl_url()` to accept optional `pub_date` parameter and use GitHub Commits API timestamp for commits URLs instead of current time.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GitHub blob title from Readability | GitHub Contents API + H1 extraction | Phase 8 | More accurate title from actual file content |
| pub_date = crawl time | pub_date = commit time for commits URLs | Phase 8 | Accurate timestamps for version-controlled content |
| Generic URL fetch | URL-type detection + strategy routing | Phase 8 | Better metadata for GitHub-specific URLs |

## Open Questions

1. **Should we cache GitHub API responses?**
   - What we know: Rate limit is 60/hour unauthenticated; Contents API returns same data for same path
   - What's unclear: Cache TTL? In-memory or database-backed cache?
   - Recommendation: Use existing `is_cache_fresh()` pattern from `src/github.py` with 1-hour TTL for contents metadata

2. **How to handle branch detection in commits URLs?**
   - What we know: Commits URL can be `github.com/{owner}/{repo}/commits/{branch}` without a path
   - What's unclear: How to get "latest commit" for entire branch vs. a specific path
   - Recommendation: If no path in URL, use Commits API without `path` param to get branch HEAD

## Environment Availability

**Step 2.6: SKIPPED (no external dependencies identified)**

This phase modifies existing Python code in `src/crawl.py` and `src/github.py`. No new external tools, services, or runtime dependencies are required. All required libraries (httpx, re) are already in use.

## Sources

### Primary (HIGH confidence)
- GitHub Contents API verified via httpx call to `api.github.com/repos/github/docs/contents/README.md`
- GitHub Commits API verified via httpx call with `path` parameter
- Rate limit info verified via `api.github.com/rate_limit` endpoint
- Markdown H1 regex verified with Python `re.search()`
- URL patterns verified with Python `re.match()`

### Secondary (MEDIUM confidence)
- `src/github.py` patterns (existing code, follows GitHub API docs conventions)
- `src/crawl.py` patterns (existing code, uses standard httpx)

### Tertiary (LOW confidence)
- None required — all findings verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing project patterns only, no new dependencies
- Architecture: HIGH — all patterns verified with Python execution
- Pitfalls: HIGH — based on existing code patterns and API behavior

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (GitHub API behavior is stable; rate limits documented)
