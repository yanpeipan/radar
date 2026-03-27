# Feature Research: Feed Auto-Discovery

**Domain:** RSS/Atom feed auto-discovery for website URLs
**Researched:** 2026-03-27
**Confidence:** HIGH (feed discovery is well-documented standard; WebSearch unavailable - using canonical knowledge)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| HTML `<link>` tag parsing | Universal standard (RSS Advisory Board, Atom spec). All major feed readers do this. | LOW | Parse `<head>` for `rel="alternate"` links with `type="application/rss+xml"`, `type="application/atom+xml"`, or `type="application/rdf+xml"`. Existing httpx + BeautifulSoup stack can handle this. |
| Well-known path probing | Many sites don't advertise in HTML but host feeds at predictable paths. Users expect "it found my feed at /feed". | LOW | Common paths: `/feed`, `/feed/`, `/rss`, `/rss.xml`, `/feed.xml`, `/index.xml`, `/atom.xml`, `/rdf.xml`. Try each with HEAD/GET request checking for XML content-type. |
| Multiple feed detection | Sites often have multiple feeds (full content, summaries, categories). Users expect "found 3 feeds". | LOW | Collect all discovered `<link>` tags. Present as list for user selection. |
| Full feed type support | Users have feeds in RSS 0.90-2.0, Atom 0.3/1.0, CDF, RDF formats. feedparser already handles all these. | LOW | feedparser.parse() accepts any of these. Only need to discover URLs. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `discover <url>` standalone command | "Just check what feeds exist" without committing. Useful for exploration. | LOW | New CLI command that lists feeds without subscribing. Natural fit with existing provider pattern. |
| `--automatic` flag (subscribe all without prompting) | Power user automation. "Add all category feeds from this site". | LOW | Simple boolean. If True, auto-subscribe all discovered feeds. If False, list and prompt. |
| Configurable depth for hierarchy discovery | Balance between thoroughness and speed/bandwidth. | MEDIUM | Depth=1 (default): only parse `<head>` of given URL. Depth=2+: also probe paths and follow internal links. |
| Feed preview before subscription | Show article count, last updated, title before committing. | LOW | Parse discovered feed, extract metadata. Reuse existing feed_meta() pattern. |
| WordPress-style query param detection | WordPress uses `/?feed=rss` style URLs. Many sites run WP. | LOW | Detect `?feed=` query params. Try variations. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Recursive site crawling for feeds | "Find all feeds on this site" sounds powerful. | HIGH | Crawling entire site is slow, potentially disrespectful (hits many pages), and rarely needed. Most sites advertise feeds in `<head>`. |
| Real-time/automatic feed updates on discovery | "Just keep discovering new feeds". | HIGH | Adds complexity (background processes, scheduling), storage concerns, and user surprise. Discovery should be explicit, not automatic background behavior. |
| Social media/discussion platform discovery | "Find feeds from Twitter, Reddit, etc." | MEDIUM | These don't use standard RSS/Atom. Would require platform-specific APIs (often restricted). Outside core RSS use case. |
| Feed validation scoring/ranking | "Rank feeds by quality". | MEDIUM | Subjective. What constitutes "quality" varies by user. Adds ML/complexity without clear benefit. |

## Feature Dependencies

```
Feed Auto-Discovery (new)
    ├──requires──> HTML link tag parsing (new)
    │                  └──requires──> httpx fetch page (reuse existing httpx)
    │                  └──requires──> BeautifulSoup parse <head> (reuse existing stack)
    │
    ├──requires──> Well-known path probing (new)
    │                  └──requires──> httpx HEAD/GET requests (reuse existing)
    │                  └──requires──> Content-Type validation (reuse existing RSSProvider.match pattern)
    │
    └──requires──> Multiple feed listing (new)
                     └──requires──> User selection CLI (reuse existing click patterns)
```

### Dependency Notes

- **HTML link tag parsing requires httpx fetch page:** Existing httpx stack is available. Need to fetch website URL (not feed URL) and parse HTML.
- **Well-known path probing reuses RSSProvider.match:** The pattern of checking Content-Type headers is already implemented. Reuse for probing paths.
- **Multiple feed listing enhances `feed add --discover`:** Existing `feed add` command is the downstream consumer of discovery.

## MVP Definition

### Launch With (v1.9)

Minimum viable product - what is needed to validate the concept.

- [ ] **HTML `<link>` tag parsing** - The standard autodiscovery method. Fetch website HTML, parse `<head>` for `<link rel="alternate">` tags with feed types. **Essential** - this is the primary discovery method.
- [ ] **Well-known path probing** - Fallback for sites that don't advertise in HTML. Try `/feed`, `/feed.xml`, `/atom.xml`, `/rss.xml`, `/rss`. **Essential** - many popular sites still use this.
- [ ] **Multiple feed listing** - Display all discovered feeds with titles so user can choose. **Essential** - otherwise discovery is not useful.
- [ ] **`discover <url>` command** - Standalone command to just discover without subscribing. **Essential** - the milestone spec explicitly calls for this.
- [ ] **`feed add <url> --discover` (default on)** - Integrate discovery into `feed add`. Default to discover= True. **Essential** - per milestone spec.

### Add After Validation (v1.9.x)

Features to add once core is working.

- [ ] **`--automatic` flag** - Auto-subscribe all discovered feeds without prompting. Lower priority since most users want to review before subscribing.
- [ ] **Feed preview** - Show article count, last updated before subscription decision. Nice UX but not critical.
- [ ] **Depth configuration** - Add `--depth N` option for hierarchy crawling later if users request it.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Recursive site crawling** - Only if users explicitly request and accept the speed/bandwidth tradeoff.
- [ ] **OPML import/export** - Already in backlog, orthogonal to discovery.
- [ ] **Read/unread state** - Already in backlog, orthogonal to discovery.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| HTML `<link>` tag parsing | HIGH - universal standard | LOW | P1 |
| Well-known path probing | HIGH - common fallback | LOW | P1 |
| Multiple feed listing | HIGH - enables user choice | LOW | P1 |
| `discover <url>` command | HIGH - milestone requirement | LOW | P1 |
| `feed add --discover` integration | HIGH - milestone requirement | LOW | P1 |
| `--automatic` flag | MEDIUM - power user feature | LOW | P2 |
| Feed preview | MEDIUM - UX improvement | LOW | P2 |
| Depth configuration | LOW - advanced use case | MEDIUM | P3 |
| Recursive crawling | LOW - rarely needed | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Inoreader | Feedly | NewsBlur | Our Approach |
|---------|-----------|--------|----------|--------------|
| HTML `<link>` parsing | Yes | Yes | Yes | Implement as primary method |
| Well-known paths | Yes | Yes | Yes | Implement as fallback |
| `discover` command | "Discover" tab | "Discover" section | Feed search | New `discover <url>` CLI command |
| Auto-subscribe option | Yes (auto-follow) | Yes | Yes | `--automatic` flag |
| Depth/crawl options | Limited | Limited | None | Depth=1 default, configurable later |

## Implementation Notes for Existing Stack

### Reuse Opportunities

1. **httpx** - Already used for HTTP requests. Fetch website HTML (not feed) via `httpx.get(url, headers=BROWSER_HEADERS)`.

2. **BeautifulSoup4** - Already in stack. Parse HTML `<head>` for `<link>` tags.

3. **feedparser** - Already handles all feed types (RSS 0.90-2.0, Atom 0.3/1.0, CDF, RDF). Only need to discover URLs; feedparser already registered in providers.

4. **Provider pattern** - RSSProvider.match() already checks Content-Type. Reuse pattern for path probing validation.

5. **Existing CLI patterns** - click decorators, Rich progress bars already in use.

### New Components Needed

1. **feed_discovery.py** (application layer) - Core discovery logic:
   - `discover_feeds(url: str) -> list[DiscoveredFeed]`
   - `probe_well_known_paths(base_url: str) -> list[DiscoveredFeed]`
   - `parse_html_autodiscovery(html: str, base_url: str) -> list[DiscoveredFeed]`

2. **CLI integration:**
   - New `discover` command in `src/cli/feed.py`
   - Modify `feed add` with `--discover` flag (default=True)

3. **Storage integration:**
   - DiscoveredFeed model (url, title, type, feed_url)
   - Optional: store discovered feeds temporarily vs. subscribe immediately

## Sources

- [RSS Advisory Board - Autodiscovery](https://www.rssboard.org/autodiscovery) (HIGH confidence - RSS standard documentation)
- [Atom Specification - Link Elements](https://datatracker.ietf.org/doc/html/rfc4287#section-4.2.7) (HIGH confidence - IETF standard)
- [feedparser Documentation](https://feedparser.readthedocs.io/en/latest/) (HIGH confidence - already in stack)
- [WHATWG - Link Types](https://www.whatwg.org/specs/web-apps/current-work/multipage/link-types.html#link-type-alternate) (HIGH confidence - WHATWG standard)

---

*Feature research for: Feed Auto-Discovery (v1.9 milestone)*
*Researched: 2026-03-27*
