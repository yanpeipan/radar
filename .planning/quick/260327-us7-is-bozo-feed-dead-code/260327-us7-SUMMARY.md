# 260327-us7-SUMMARY: 废弃 is_bozo_feed dead code

## Status: ✅ Complete

## Changes Made

| File | Change |
|------|--------|
| `src/discovery/fetcher.py` | Removed `is_bozo_feed()` function and unused `feedparser` import |
| `src/discovery/__init__.py` | Removed `is_bozo_feed` from import |

## Rationale

`is_bozo_feed()` was defined but never called anywhere in the codebase (no callers in src/, tests/, or cli/). It was dead code that used feedparser to check if a feed was malformed — this validation was never wired into the discovery flow.

After removal:
- `validate_feed()` remains (uses httpx HEAD request for Content-Type validation)
- `feedparser` was only used by `is_bozo_feed`, so it was also removed

## Verification

- `from src.discovery.fetcher import validate_feed` — OK
- `from src.discovery import discover_feeds` — OK
- `grep "is_bozo_feed" src/discovery/` — 0 occurrences
- `grep "feedparser" src/discovery/fetcher.py` — 0 occurrences (was only used by is_bozo_feed)
