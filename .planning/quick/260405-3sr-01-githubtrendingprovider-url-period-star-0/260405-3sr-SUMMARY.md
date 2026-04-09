# Quick Plan 260405-3sr: GitHub Trending Provider Enhancements

## Summary

Implemented URL period detection and star parsing fixes for GitHubTrendingProvider.

## Changes Made

### 1. Added `_parse_period_from_url` helper (Task 1)
- Added `urllib.parse` import
- New method `_parse_period_from_url(url: str) -> str | None`
- Parses `since=` query param from GitHub trending URLs
- Returns 'daily', 'weekly', 'monthly' for valid values
- Returns None for invalid or missing `since=` values

### 2. Modified `fetch_articles` for single period (Task 2)
- Calls `_parse_period_from_url(feed.url)` at start
- If period detected: fetches only that single period
- If None: fetches all 3 periods (backward compatible)
- Renamed loop variable from `period` to `selected_period` to avoid shadowing

### 3. Fixed star/fork parsing (Task 3)
- Wrapped stars and forks parsing in try/except blocks
- Uses `int(float())` pattern for robustness
- Defaults to 0 on any parsing failure
- Ensures 0, not NaN, on malformed input

## Verification

```
$ uv run python -c "from src.providers.github_trending_provider import GitHubTrendingProvider; p = GitHubTrendingProvider()
... print('daily:', p._parse_period_from_url('https://github.com/trending?since=daily'))
... print('weekly:', p._parse_period_from_url('https://github.com/trending?since=weekly'))
... print('monthly:', p._parse_period_from_url('https://github.com/trending?since=monthly'))
... print('invalid:', p._parse_period_from_url('https://github.com/trending?since=invalid'))
... print('none:', p._parse_period_from_url('https://github.com/trending'))"
daily: daily
weekly: weekly
monthly: monthly
invalid: None
none: None
```

## Commit

`61e5214` - feat(github_trending): add URL period detection and fix star parsing
