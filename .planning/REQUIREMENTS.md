# v2.1 Requirements — 使用最佳实践重构 src/discovery & src/providers

**Goal:** Clean up and harden the feed discovery architecture using best practices.

---

## REFACTORING CATEGORIES

### Architecture (ARCH)

- [ ] **ARCH-01**: `providers.discover()` uses `feed_meta()` pattern for validation instead of `parse_feed()`
  - `feed_meta()` returns `FeedMetaData` with url, title, feed_type, source, page_url
  - `parse_feed()` raises on invalid feeds; `feed_meta()` returns `None` on failure
  - Change `providers.discover()` to call `feed_meta()` not `parse_feed()`

- [ ] **ARCH-02**: `discover_feeds()` always returns provider-verified feeds
  - `DiscoveredResult.feeds` only contains feeds that a provider confirms it can handle
  - Remove feeds from `deep_crawl()` that no provider matches

- [ ] **ARCH-03**: `deep_crawl()` delegates feed validation entirely to providers
  - `deep_crawl()` does URL discovery only; providers handle validation
  - `page_feeds = providers.discover()` on each crawled page
  - `max_depth <= 1` path also uses `providers.discover()` not inline validation

- [ ] **ARCH-04**: `match()` edge cases resolved — `response=None` handling
  - All providers' `match()` handles `response=None` gracefully
  - When `response=None`, match is URL-only (no new HTTP requests)
  - Document this constraint in `ContentProvider` docstring

### Constants & Code Quality (QUAL)

- [ ] **QUAL-01**: `src/constants.py` `BROWSER_HEADERS` used consistently everywhere
  - All HTTP requests in `src/providers/`, `src/discovery/`, `src/application/` use `BROWSER_HEADERS`
  - No hardcoded User-Agent strings anywhere in `src/`

- [ ] **QUAL-02**: Async patterns consistent across providers
  - All providers use `asyncio.to_thread()` for blocking HTTP calls
  - No blocking `Fetcher.get()` calls in async functions

- [ ] **QUAL-03**: Clean up duplicate feed validation code
  - `discovery/fetcher.py`'s `validate_feed()` and `_quick_validate_feed_sync()` in RSSProvider overlap
  - Consolidate into a single shared validation utility

### API Surface (API)

- [ ] **API-01**: `ContentProvider.parse_feed()` docstring clarifies it raises on failure
  - `parse_feed()` called only after `match()` confirms the provider handles the URL
  - Use `feed_meta()` for non-throwing validation

- [ ] **API-02**: `providers.discover()` returns only unique feeds by URL
  - Deduplicate feeds by URL across all providers

- [ ] **API-03**: `DiscoveredFeed.valid` field semantics clarified
  - `valid=True` means provider confirmed handleable
  - `valid=False` means discovered but not yet validated
  - No feed with `valid=False` should reach `register_feed()`

---

## OUT OF SCOPE

- New provider types
- Changes to storage layer
- Changes to search/ranking
- OPML import/export
- Read/unread state

---

## Traceability

| REQ-ID | Phase | Status |
|---------|-------|--------|
| ARCH-01 | Phase 45 | Pending |
| ARCH-02 | Phase 45 | Pending |
| ARCH-03 | Phase 45 | Pending |
| ARCH-04 | Phase 46 | Pending |
| QUAL-01 | Phase 47 | Pending |
| QUAL-02 | Phase 47 | Pending |
| QUAL-03 | Phase 47 | Pending |
| API-01 | Phase 46 | Pending |
| API-02 | Phase 45 | Pending |
| API-03 | Phase 45 | Pending |
