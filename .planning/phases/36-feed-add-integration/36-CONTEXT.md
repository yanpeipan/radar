# Phase 36: Feed Add Integration - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning
**Mode:** Auto (discuss skipped via --auto)

<domain>
## Phase Boundary

Users can add feeds via discovery using `feed add <url> --discover [on/off] --automatic [on/off] --discover-deep [n]`

</domain>

<decisions>
## Implementation Decisions

### DISC-06 Implementation
- **D-01:** `--discover on` (default): Run feed discovery before subscription
- **D-02:** `--automatic off` (default): List discovered feeds and prompt user to select
- **D-03:** `--discover-deep` passed to discovery service (depth > 1 shows "not yet implemented" until Phase 37)

### Selection UI (when --automatic off)
- **D-04:** Numbered list display (same Rich Table as `discover` command)
- **D-05:** "Subscribe to all" / "Select individually" / "Cancel" prompt
- **D-06:** Individual selection via comma-separated numbers or ranges (e.g., "1,3,5-7")

### Edge Cases
- **D-07:** If URL is already a direct feed URL: still run discovery to find additional feeds on that page
- **D-08:** If no feeds discovered: show error message "No feeds found at <url>. Try providing a website URL instead of a feed URL." and do NOT subscribe
- **D-09:** Deep crawl stub: if `--discover-deep > 1`, show "Deep crawling is not yet implemented. Use depth=1." and proceed with depth=1 discovery

### Integration Points
- **D-10:** Reuse `_display_feeds()` from `src/cli/discover.py` for consistency
- **D-11:** Reuse `discover_feeds()` from `src/discovery/__init__.py`
- **D-12:** Add options to existing `feed_add` function in `src/cli/feed.py`

</decisions>

<canonical_refs>
## Canonical References

### Discovery Module (Phase 34)
- `src/discovery/__init__.py` — `discover_feeds(url)`, `DiscoveredFeed` dataclass
- `src/discovery/models.py` — `DiscoveredFeed` definition

### Discovery CLI (Phase 35)
- `src/cli/discover.py` — `_display_feeds()` Rich Table pattern, `--discover-deep` flag

### Feed CLI (existing)
- `src/cli/feed.py` — `feed_add` command structure

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_display_feeds()` in `src/cli/discover.py`: Rich Table with color-coded feed types
- `discover_feeds()` in `src/discovery/__init__.py`: returns `list[DiscoveredFeed]`
- `DiscoveredFeed` dataclass: url, title, feed_type, source, page_url

### Established Patterns
- `uvloop.run()` for async CLI commands (not @click.async_command)
- `click.secho(..., err=True, fg="red")` for error messages
- Click IntRange validation for numeric options

### Integration Points
- `feed add` command in `src/cli/feed.py` (lines 81-108)
- `discover_or_default()` from `src/providers/__init__.py` (used for provider detection)

</code_context>

<specifics>
## Specific Ideas

No specific user requirements — standard CLI integration. Use codebase conventions.

</specifics>

<deferred>
## Deferred Ideas

- Deep crawling BFS (Phase 37) — `--discover-deep > 1` stubs to "not yet implemented" in Phase 36
- robots.txt respecting during discovery (Phase 37)

</deferred>
