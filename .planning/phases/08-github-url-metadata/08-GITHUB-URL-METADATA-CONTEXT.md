# Phase 8: GitHub URL Metadata - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Improve metadata extraction for crawled GitHub URLs:
1. GitHub blob pages: better title extraction and format
2. GitHub commits pages: use latest commit time as pub_date
3. GitHub file URLs: detect URL type before fetching, use appropriate extraction strategy

This is Phase 8, building on Phase 3 (Web Crawling) decisions.

</domain>

<decisions>
## Implementation Decisions

### GitHub URL Detection (Before Fetch)
- **D-GH01:** Detect GitHub URL type BEFORE fetching, using URL pattern matching
  - Blob URLs: `github.com/{owner}/{repo}/blob/{branch}/{path}`
  - Commits URLs: `github.com/{owner}/{repo}/commits/{branch}/{path}`
  - Use existing regex from `_convert_github_blob_to_raw()` as base, extend to cover commits
  - Detect early to choose appropriate extraction strategy

### GitHub API for File Metadata
- **D-GH02:** For GitHub blob URLs, use GitHub Contents API (`/repos/{owner}/{repo}/contents/{path}`) to get file metadata
  - Falls back to raw markdown parsing if API fails or is rate-limited
  - Parse owner/repo from URL using `src/github.py` patterns

### Title Format for GitHub Files
- **D-GH03:** Title format for GitHub blob pages:
  - `{owner}/{repo} / {first H1 in file}` if H1 exists
  - `{owner}/{repo} / {filename}` if no H1
  - Extract H1 from markdown by finding first `# heading` line
  - If parsing fails, use `{owner}/{repo} / {filename}` as fallback

### Pub_date for GitHub Commits Pages
- **D-GH04:** For GitHub commits URLs, use latest commit time as `pub_date`
  - Detect commits page URL: `github.com/{owner}/{repo}/commits/...`
  - Use GitHub Commits API (`/repos/{owner}/{repo}/commits/sha`) to get latest commit time
  - Fall back to current time if API fails or unavailable

### Error Handling
- **D-GH05:** Graceful fallback on GitHub API failure
  - If GitHub API fails (rate limit, network error), fall back to raw URL fetch
  - For title: use filename as title
  - For pub_date: use current time
  - Log warning when falling back

### Code Organization
- **D-GH06:** GitHub-specific URL handling in `src/crawl.py`
  - Add helper functions: `is_github_blob_url()`, `is_github_commits_url()`
  - Add `fetch_github_file_metadata()` using GitHub Contents API
  - Keep web crawling logic centralized in crawl.py

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `src/crawl.py` — Existing crawl.py with `_convert_github_blob_to_raw()` pattern
- `src/github.py` — Existing `parse_github_url()` and GitHub API integration patterns
- `.planning/phases/03-web-crawling/03-CONTEXT.md` — Original Phase 3 decisions (Readability, robots.txt, rate limiting)
- `.planning/STATE.md` — Project decisions and history

</canonical_refs>

<codebase_context>
## Existing Code Insights

### Reusable Assets
- `src/crawl.py:_convert_github_blob_to_raw()` — Existing GitHub URL detection regex pattern
- `src/github.py:parse_github_url()` — GitHub URL parsing (owner/repo extraction)
- `src/github.py` — GitHub API client with rate limiting and token handling

### Established Patterns
- Rate limiting (2s between same host) should apply to GitHub API calls too
- Error isolation: try/except per operation, continue on failure
- Fallback chain for resilience

### Integration Points
- Add GitHub URL detection before the main fetch in `crawl_url()`
- Add `pub_date` parameter to `crawl_url()` return dict
- Pass `pub_date` to article insert in `crawl_url()`

</codebase_context>

<deferred>
## Deferred Ideas

- GitHub API rate limit handling (60 req/hour unauthenticated) — consider adding GITHUB_TOKEN support for higher limits
- Playwright rendering for GitHub blob pages — eliminates API calls but adds browser overhead
- GitHub PR/issues page support — different URL patterns, different metadata needs

</deferred>
