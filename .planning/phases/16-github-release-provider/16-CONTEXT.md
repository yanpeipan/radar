# Phase 16: GitHubReleaseProvider - Context

**Gathered:** 2026-03-24 (discuss mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a new GitHubReleaseProvider that uses PyGithub's repo.get_latest_release() to fetch GitHub release information. This is a NEW provider separate from the existing GitHubProvider — they coexist, both matching github.com URLs but with different priorities.

</domain>

<decisions>
## Implementation Decisions

### Provider Identity
- **D-01:** New provider class: `GitHubReleaseProvider` in `src/providers/github_release_provider.py`
- **D-02:** New tag parser class: `ReleaseTagParser` in `src/tags/release_tag_parser.py`
- **D-03:** Both self-register via `PROVIDERS.append()` and `TAG_PARSERS.append()` at module import time (same pattern as existing providers)

### URL Matching
- **D-04:** GitHubReleaseProvider.match() matches the same github.com URLs as GitHubProvider (HTTPS and SSH formats)
- **D-05:** Both providers can match the same URL — priority resolves which runs first

### Priority
- **D-06:** GitHubReleaseProvider priority = 200 (higher than GitHubProvider's 100)
- **D-07:** GitHubReleaseProvider runs first for all GitHub URLs — release-specific provider takes precedence

### Crawl Behavior
- **D-08:** GitHubReleaseProvider.crawl() calls `repo.get_latest_release()` via PyGithub — same as GitHubProvider uses internally
- **D-09:** Returns `List[Raw]` with single release dict: {tag_name, name, body, html_url, published_at}
- **D-10:** Empty list on any error (rate limit, not found, etc.) — error isolation same as GitHubProvider

### Parse Behavior
- **D-11:** Same Article structure as GitHubProvider.parse():
  - title = tag_name or name
  - link = html_url
  - guid = tag_name
  - pub_date = published_at
  - description = body
  - content = None

### Tag Parsing
- **D-12:** GitHubReleaseProvider uses ReleaseTagParser (not DefaultTagParser)
- **D-13:** ReleaseTagParser extracts:
  - `owner` tag: extracted from URL via parse_github_url()
  - `release` tag: always added for release articles
  - Version tags: extracted from tag_name using regex (e.g., v1.2.3 → v1, v1.2, v1.2.3)
  - Release type tags: `major-release` if tag matches major version pattern, `minor-release`, `bugfix-release`

### Storage
- **D-14:** No DB storage — GitHubReleaseProvider returns articles only, same as GitHubProvider

### File Changes
- **D-15:** Create `src/providers/github_release_provider.py` — GitHubReleaseProvider class
- **D-16:** Create `src/tags/release_tag_parser.py` — ReleaseTagParser class

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Provider Architecture (Phase 12-13)
- `src/providers/base.py` — ContentProvider Protocol, Article/Raw/TagParser types
- `src/providers/__init__.py` — ProviderRegistry, discover(), PROVIDERS list
- `src/providers/github_provider.py` — Existing GitHubProvider (priority=100) for reference
- `src/tags/__init__.py` — TAG_PARSERS list, chain_tag_parsers()

### GitHub Integration (Phase 15)
- `src/github_utils.py` — parse_github_url() utility for extracting owner/repo
- `src/github_ops.py` — DB operations (NOT used by providers, but related to github_releases table)

### Tag System (Phase 13)
- `src/tags/default_tag_parser.py` — Example tag parser for reference
- `src/tag_rules.py` — match_article_to_tags() for rule structure reference

### Dependencies
- `pyproject.toml` — PyGithub already added in Phase 15

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `parse_github_url()` from github_utils.py — extracts owner/repo from GitHub URLs
- PyGithub singleton pattern from github_provider.py — _get_github_client() for API calls
- Release dict structure already defined: {tag_name, name, body, html_url, published_at}
- Article dict structure from base.py

### Established Patterns
- Self-registration via module-level PROVIDERS.append()
- Error isolation: crawl() returns empty list on failure
- Priority-based provider selection (highest priority that matches wins)
- Tag parser returns list of tag strings
- chain_tag_parsers() for combining multiple tag parsers

### Integration Points
- GitHubReleaseProvider will register alongside GitHubProvider
- Both match github.com URLs but GitHubReleaseProvider (200) runs first
- ReleaseTagParser is a separate tag parser in the chain

</code_context>

<deferred>
## Deferred Ideas

- GitHubProvider deprecation — once GitHubReleaseProvider is stable, consider deprecating GitHubProvider (separate phase)
- github_releases table cleanup — if no providers use github_ops.py storage, table could be dropped (separate phase)

</deferred>
