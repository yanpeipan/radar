# Phase 34-03 Summary: discover_feeds() async entry point

## Completed

Implemented `discover_feeds()` async entry point in `src/discovery/__init__.py`.

## Implementation

### discover_feeds(url: str) -> list[DiscoveredFeed]
Main async entry point that:
1. Normalizes input URL (adds https:// scheme if missing)
2. Fetches page HTML using httpx.AsyncClient with BROWSER_HEADERS
3. Parses HTML for autodiscovery `<link>` tags via `parse_link_elements()`
4. Validates autodiscovery feeds concurrently, filtering out bozo feeds
5. Falls back to well-known paths if no autodiscovery feeds found
6. Validates well-known path candidates concurrently

### Helper Functions
- `normalize_url(url: str) -> str`: Adds https:// scheme if missing
- `probe_well_known_paths(page_url: str) -> list[str]`: Generates candidate URLs from WELL_KNOWN_PATHS
- `validate_and_wrap(url, page_url, source) -> DiscoveredFeed | None`: Validates feed URL and wraps in DiscoveredFeed

## Exports
- `discover_feeds`: Main async entry point
- `DiscoveredFeed`: Dataclass from models
- `WELL_KNOWN_PATHS`: Tuple of well-known feed paths

## Reused Components
- `BROWSER_HEADERS` from `src.providers.rss_provider`
- `parse_link_elements` from `src.discovery.parser`
- `validate_feed` and `is_bozo_feed` from `src.discovery.fetcher`
- `WELL_KNOWN_PATHS` from `src.discovery.common_paths`
- `DiscoveredFeed` from `src.discovery.models`

## Verification
- `discover_feeds` is an async coroutine function with `url` parameter
- All required well-known paths present in WELL_KNOWN_PATHS
