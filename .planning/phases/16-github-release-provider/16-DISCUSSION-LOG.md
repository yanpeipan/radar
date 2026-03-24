# Phase 16: GitHubReleaseProvider - Discussion Log

**Date:** 2026-03-24
**Phase:** 16-GitHubReleaseProvider
**Mode:** discuss
**Areas analyzed:** Provider Identity, URL Matching, Priority, Crawl Behavior, Tag Parsing

## Discussion Summary

### Decisions Made

| Area | Decision | Rationale |
|------|----------|-----------|
| Provider Identity | New GitHubReleaseProvider separate from GitHubProvider | Allows coexistence with different focuses |
| URL Matching | Same github.com URLs as GitHubProvider | Both can handle same URLs, priority decides |
| Priority | 200 (higher than GitHubProvider's 100) | Release-specific provider takes precedence |
| Crawl Scope | Latest release only | Simple, focused behavior |
| Storage | Return articles only, no DB storage | Consistent with provider pattern |
| Tag Parser | ReleaseTagParser (not DefaultTagParser) | Extracts release-specific semantic tags |
| Tag Content | owner, release, version, release-type tags | Semantic tagging for release categorization |

### User Selections

1. **New GitHubReleaseProvider** — separate from existing GitHubProvider
2. **Same URLs** — both providers match github.com URLs
3. **Priority 200** — higher than GitHubProvider's 100
4. **Latest release only** — using repo.get_latest_release()
5. **Return articles only** — no DB storage
6. **Release-specific tagger** — ReleaseTagParser extracts semantic tags
7. **You decide** — tag patterns left to implementer's discretion

## Corrections

None — all assumptions confirmed by user.

## Auto-Resolved

None — no auto mode used.

## External Research

None required — existing codebase patterns sufficient.

