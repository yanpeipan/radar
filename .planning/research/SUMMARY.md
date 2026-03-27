# Project Research Summary

**Project:** v1.9 Automatic Discovery Feed
**Domain:** RSS/Atom feed auto-discovery from website URLs (RSS reader CLI)
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

This is a feed auto-discovery feature for an existing RSS reader CLI. The tool discovers RSS/Atom/RDF feeds from a website URL without requiring users to know the exact feed URL. Experts implement this as a two-stage process: first parse HTML `<head>` for `<link rel="alternate">` tags (the W3C standard autodiscovery method), then fall back to probing well-known URL paths like `/feed`, `/rss`, `/atom.xml`.

**No new library dependencies are required.** The existing stack (httpx for HTTP fetching, BeautifulSoup4 for HTML parsing, feedparser for feed validation, urllib.parse for URL resolution) is sufficient. Feed auto-discovery is custom logic, not a specialized library feature.

The recommended approach is to build a separate `src/discovery/` service module that produces feed URLs consumable by the existing `add_feed()` flow. Discovery is NOT a Provider plugin -- it is a URL-to-URLs transformation that does not fit the Provider pattern (which is URL-to-Articles). Key risks include infinite crawl loops (mitigate with visited-set + depth limit), dead feeds being subscribed (mitigate with validation before DB insert), and relative URL resolution failures (mitigate with proper urljoin).

## Key Findings

### Recommended Stack

No new dependencies. All required technologies are already in the stack:

- **httpx (0.28.x)** -- HTTP client for fetching HTML pages (async/sync, HTTP/2)
- **BeautifulSoup4 (4.12.x)** -- HTML parsing for `<link>` tag extraction in `<head>`
- **feedparser (6.0.x)** -- Validates discovered feeds by parsing; handles RSS 0.9x-2.0, Atom 0.3/1.0, CDF, RDF
- **urllib.parse (stdlib)** -- URL resolution (urljoin) for relative links in `<link href>`
- **lxml (6.0.x)** -- Faster HTML parser backend for BeautifulSoup (already installed)

**NOT recommended:** feedfinder2 (abandoned), Scrapy (overkill), Selenium (not needed), Playwright for `<link>` tags (basic HTML parsing sufficient).

### Expected Features

**Must have (table stakes):**
- HTML `<link>` tag parsing -- the W3C standard autodiscovery method. Parse `<head>` for `rel="alternate"` links with `type="application/rss+xml"`, `type="application/atom+xml"`, or `type="application/rdf+xml"`.
- Well-known path probing -- fallback for sites without autodiscovery links. Try `/feed`, `/feed/`, `/rss`, `/rss.xml`, `/atom.xml`, `/feed.xml`, `/index.xml`.
- Multiple feed listing -- display all discovered feeds with titles so user can choose which to subscribe.
- `discover <url>` command -- standalone CLI command to just discover without subscribing.
- `feed add <url> --discover` (default on) -- integrate discovery into `feed add` as the default behavior.

**Should have (competitive):**
- `--automatic` flag -- auto-subscribe all discovered feeds without prompting (power user feature).
- Feed preview -- show article count, last updated before subscription decision.
- `--depth` configuration -- balance between thoroughness and speed for hierarchy crawling.

**Defer (v2+):**
- Recursive site crawling -- rarely needed, slow, potentially disrespectful to sites.
- OPML import/export -- orthogonal to discovery.
- Read/unread state -- orthogonal to discovery.

### Architecture Approach

Discovery is a separate service module (`src/discovery/`), NOT a Provider plugin. The Provider pattern is designed for URL-to-Articles; discovery is URL-to-URLs. This distinction is critical to avoid architectural misfits.

**Major components:**
1. `src/discovery/models.py` -- `DiscoveredFeed` dataclass (url, title, feed_type, source, page_url)
2. `src/discovery/parser.py` -- HTML `<link>` element parsing from `<head>`
3. `src/discovery/common_paths.py` -- Well-known feed path heuristics
4. `src/discovery/fetcher.py` -- BFS crawler with depth limit and cycle detection
5. `src/discovery/__init__.py` -- `discover_feeds()` async function entry point

CLI layer calls `discover_feeds()`, then passes results to existing `add_feed()`. No changes to Provider or Storage layers required.

### Critical Pitfalls

1. **Infinite crawl loops** -- Sites with hub-and-spoke architectures create cycles. Prevention: maintain visited URL set, hard depth limit (default=1, max=5), total timeout per root URL.

2. **Subscribing to dead/empty feeds** -- Autodiscovery links may point to defunct feeds. Prevention: validate feed URL before subscribing (fetch and require at least 1 entry or valid structure). Treat 404/410 as "not a real feed."

3. **Missing autodiscovery tags** -- Many legitimate sites don't implement `<link>` autodiscovery. Prevention: always fall back to well-known path probing. Limit to 3-5 patterns to avoid excessive requests.

4. **Relative feed URLs** -- HTML allows `<link href="/feed.xml">`. Prevention: always resolve with `urllib.parse.urljoin(page_url, href)`, handle `<base href>` overrides.

5. **Case-sensitive attribute matching** -- Real sites use mixed case (`type="Application/Rss+Xml"`). Prevention: normalize `type.lower()` and `rel.lower()` before matching. Use BeautifulSoup (not regex) for parsing.

## Implications for Roadmap

Based on research, the following phase structure is recommended:

### Phase 1: Discovery Module Core
**Rationale:** Must establish the fundamental discovery logic before any CLI or application integration. Dependencies: None (greenfield module).
**Delivers:** `src/discovery/` package with `DiscoveredFeed` model, `parse_link_elements()`, `try_common_paths()`, `discover_feeds(depth=1)`.
**Implements:** STACK (httpx fetch, BeautifulSoup parsing, feedparser validation), avoids Pitfalls 3 (heuristic fallback), 4 (relative URL resolution), 5 (case normalization).
**Research flags:** None -- well-documented W3C standard with established implementation patterns.

### Phase 2: CLI Integration
**Rationale:** `discover <url>` command is explicitly in the milestone spec. CLI must be working before application integration. Depends on Phase 1.
**Delivers:** `discover` command (read-only), `--discover/--no-discover` and `--depth` options on `feed add`, `--automatic` flag.
**Uses:** existing click decorators, Rich progress bars.
**Addresses:** FEATURES MVP (multiple feed listing, discover command, feed add integration).
**Research flags:** None -- standard CLI patterns already in codebase.

### Phase 3: Application Layer Integration
**Rationale:** Wire `feed add --discover` to call `discover_feeds()` and pass results to `add_feed()`. Depends on Phase 2.
**Delivers:** `add_feed_with_discovery()` in `src/application/feed.py`, fully integrated `feed add <website_url>` workflow.
**Uses:** existing `add_feed()`, existing Provider discovery (`discover_or_default`).
**Avoids:** Pitfall 2 (feed validation before subscribing), Pitfall 7 (URL normalization on add).
**Research flags:** None -- application layer patterns already established.

### Phase 4: Depth > 1 Support
**Rationale:** Depth-limited crawling is explicitly mentioned in milestone spec (`--discover-deep [n]`). Only needed if Phase 1-3 discovery finds insufficient feeds. Optional enhancement.
**Delivers:** BFS crawler in `src/discovery/fetcher.py` with visited-set, depth limit, rate limiting, cycle detection.
**Avoids:** Pitfall 1 (infinite crawl loops), Pitfall 8 (honoring robots.txt during crawl).
**Research flags:** MEDIUM -- real-world crawling behavior on diverse sites needs validation.

### Phase Ordering Rationale

- Phase 1 before 2: Discovery module must exist before CLI can integrate it.
- Phase 2 before 3: CLI commands must work before application layer wires them together.
- Phase 3 before 4: Depth crawling is an enhancement, not blocking the core discovery flow.
- Grouping by architecture: discovery module (Phase 1) is separate from CLI (Phase 2) which is separate from application wiring (Phase 3).
- This order avoids all critical pitfalls: Phase 1 builds URL resolution + heuristic fallback + case normalization; Phase 3 adds feed validation before subscribe.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 4 (Depth > 1):** MEDIUM confidence. Real-world site link structures vary. Recommend validation testing on 5-10 diverse sites (WordPress, static site generators, subdirectory-based category feeds).

Phases with standard patterns (skip research-phase):
- **Phase 1:** HIGH confidence. W3C autodiscovery spec is well-documented, HTML `<link>` parsing is standard.
- **Phase 2:** HIGH confidence. CLI patterns already established in codebase.
- **Phase 3:** HIGH confidence. Application layer integration follows existing patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies. All technologies verified in existing CLAUDE.md stack. |
| Features | HIGH | Feed autodiscovery is a mature, well-understood feature domain. W3C spec + industry practice. |
| Architecture | HIGH | Clear separation between discovery (URL->URLs) and providers (URL->Articles). Proposed module structure follows single-responsibility. |
| Pitfalls | MEDIUM | WebSearch was unavailable during research. Findings rely on training data + official RSS Board spec. Recommend validation against real websites during Phase 1 implementation. |

**Overall confidence:** HIGH

### Gaps to Address

- **Real-world site testing:** No WebSearch available during research. Canonical knowledge only. Recommend Phase 1 include integration tests against 5-10 diverse real websites (WordPress, Medium, static sites, GitHub pages, subdirectory-based category feeds) to validate autodiscovery and heuristic fallback effectiveness.
- **robots.txt enforcement scope:** PITFALLS.md notes current system uses lazy mode ignoring robots.txt. Decision needed on whether Phase 4 depth crawling should honor robots.txt or remain in lazy mode like existing explicit feed fetches.
- **Feed URL canonicalization:** Duplicate feed subscription (Pitfall 7) requires URL normalization. This may need a shared utility if other parts of the codebase also need normalization.

## Sources

### Primary (HIGH confidence)
- RSS Board -- RSS Autodiscovery (https://www.rssboard.org/rss-autodiscovery) -- official autodiscovery specification
- Atom Specification RFC 4287 -- Link Elements (https://datatracker.ietf.org/doc/html/rfc4287#section-4.2.7) -- IETF standard for `<link>` in Atom feeds
- HTML5 Specification -- link element (https://html.spec.whatwg.org/multipage/semantics.html#the-link-element) -- WHATWG standard
- feedparser 6.0.x documentation -- Universal feed parser (RSS 0.9x-2.0, Atom 0.3/1.0, CDF, RDF)
- BeautifulSoup4 documentation -- HTML parsing with `<link>` tag navigation
- httpx documentation -- Async HTTP client with timeout and redirect support
- Existing project code -- `src/providers/rss_provider.py`, `src/application/fetch.py`, `src/providers/__init__.py`

### Secondary (MEDIUM confidence)
- feedparser README -- Bozo Detection -- official but brief documentation
- Common feed URL patterns -- Industry convention (/feed, /rss, /atom.xml, etc.) -- established practice
- Project PROJECT.md -- v1.9 milestone specification

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
