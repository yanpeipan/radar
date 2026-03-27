# Phase 36: Feed Add Integration - Execution Summary

**Plan:** 36-01
**Date:** 2026-03-27
**Wave:** 1
**Status:** ✅ Complete

## Changes Made

### Task 1: Modified `_display_feeds()` in `src/cli/discover.py`

- Added `numbered: bool = False` parameter to function signature
- Added `#` column when `numbered=True`
- Changed loop to `enumerate(feeds, 1)` and add index when `numbered=True`
- Backward compatible: default `numbered=False` preserves existing behavior

### Task 2: Modified `feed_add` command in `src/cli/feed.py`

**New imports added:**
- `uvloop` (already existed, now also imports `discover_feeds`, `DiscoveredFeed`)
- `from src.discovery import discover_feeds, DiscoveredFeed`
- `from src.cli.discover import _display_feeds`

**New Click options:**
- `--discover` (on/off, default: on)
- `--automatic` (on/off, default: off)
- `--discover-deep` (IntRange 1-10, default: 1)

**New helper functions:**
- `_prompt_selection(feeds: list[DiscoveredFeed]) -> list[int]`: Prompts user with "a/s/c" choices
- `_parse_selection(selection: str, max_idx: int) -> list[int]`: Parses comma-separated numbers and ranges

**Command behavior:**
- `--discover on --automatic off` (default): Runs discovery, shows numbered list via `_display_feeds(feeds, numbered=True)`, prompts for selection
- `--discover on --automatic on`: Auto-adds all discovered feeds
- `--discover off`: Original behavior (direct `add_feed()` call)
- `--discover-deep > 1`: Shows "not yet implemented" warning, proceeds with depth=1

### Task 3: Verification

- Python syntax valid in both files (AST parse)
- All new imports present
- All new Click options defined
- Helper functions defined
- `_display_feeds()` accepts `numbered` parameter

## Files Modified

| File | Changes |
|------|---------|
| `src/cli/discover.py` | Added `numbered` parameter to `_display_feeds()` |
| `src/cli/feed.py` | Added discovery options to `feed_add`, helper functions, discovery flow |

## Requirements Fulfilled (DISC-06)

- ✅ `feed add <url> --discover on` (default) runs feed discovery before subscription
- ✅ `feed add <url> --automatic on` auto-subscribes all discovered feeds
- ✅ `feed add <url> --automatic off` (default) shows numbered Rich Table and prompts selection
- ✅ `feed add <url> --discover-deep 2` shows "not yet implemented" stub
- ✅ No feeds discovered shows error and exits without subscribing
- ✅ Discovered feeds display in numbered Rich Table (via `_display_feeds(feeds, numbered=True)`)
