# Pitfalls Research

**Domain:** RSS/Atom/RDF Feed Auto-Discovery for CLI Aggregator
**Researched:** 2026-03-27
**Confidence:** MEDIUM

*Note: WebSearch tool was unavailable during research. Findings rely on training data + verified official documentation (RSS Board auto-discovery spec). LOW confidence for community patterns — recommend validation via real-world testing with actual websites.*

---

## Critical Pitfalls

### Pitfall 1: Infinite Crawl Loops

**What goes wrong:**
Auto-discovery crawls linked pages that themselves link back, creating endless loops. The crawler never terminates, exhausting HTTP requests and CPU.

**Why it happens:**
When discovering feeds from a website's homepage, the homepage may link to category feeds, which link to article pages, which link back to category feeds. Without loop detection, the crawler follows each link indefinitely. Sites with hub-and-spoke architectures (A links to B, C; B and C both link back to A) trigger this.

**How to avoid:**
- Maintain a **visited URL set** with a **max depth limit** (e.g., max 1 hop for discovery). PROJECT.md specifies "default 1 layer, configurable多层深度" — enforce this strictly.
- Track discovered feed URLs in a set; never re-fetch the same URL in a single discovery session.
- If a URL redirects, record only the final resolved URL in the visited set.
- Set a **hard timeout per URL** (e.g., 10s) and **max total discovery time** (e.g., 60s per root URL).

**Warning signs:**
- Discovery command hangs for minutes without output
- HTTP request count exceeds 10x expected pages
- Log shows repeated "Fetching same URL" messages

**Phase to address:**
- Phase that implements the discover/discover-or-default URL crawling logic
- Prevention must be built into the discovery crawler, not retrofitted

---

### Pitfall 2: Subscribing to Dead or Empty Feeds

**What goes wrong:**
Auto-discovery finds a feed URL, subscribes the user, but subsequent fetches return no articles or 404/410 errors.

**Why it happens:**
Many websites expose autodiscovery links to feeds that are: empty (no items yet), permanently removed (410 Gone), temporarily unavailable (500 errors), or redirect to other URLs that are dead. The autodiscovery link may be valid HTML but the feed behind it is defunct.

**How to avoid:**
- After discovering a feed URL, **validate it before subscribing**: attempt a fetch and require at least 1 entry or valid feed structure.
- Track HTTP status codes. Treat 404, 410, 500 as "not a real feed" and skip.
- Follow redirects during discovery but detect redirect chains > 3 hops as suspicious.
- Implement **retry with backoff** for 500-level errors (treat as transient, not invalid).

**Warning signs:**
- `feed add --discover` succeeds but `fetch` returns 0 articles repeatedly
- Logs show "Feed returned 410 Gone" or "Empty feed" entries

**Phase to address:**
- Phase that implements `feed add --discover` validation logic

---

### Pitfall 3: Missing Auto-Discovery Tags on Real Sites

**What goes wrong:**
Auto-discovery finds nothing on many legitimate websites because those sites don't implement RSS autodiscovery in their HTML `<head>`.

**Why it happens:**
The RSS Board autodiscovery spec requires `<link rel="alternate" type="application/rss+xml">` in the `<head>`. Many sites: (a) have no feed at all, (b) have feeds but no autodiscovery links, (c) use non-standard rel values (e.g., `rel="rss"` instead of `rel="alternate"`), or (d) bury the feed link in the footer with no `<head>` reference.

**How to avoid:**
- Fall back to **URL pattern heuristics** when autodiscovery finds nothing: try common feed URL patterns like `/feed`, `/rss`, `/atom.xml`, `/feed.xml`, `/rss.xml`, `/index.xml` appended to the domain.
- Limit heuristic attempts to a small set (3-5 patterns) to avoid excessive requests.
- Log when autodiscovery finds nothing vs. when heuristic succeeds — this is valuable signal for improving the tool.
- Support `--automatic` flag defaulting to off (per PROJECT.md) so users explicitly confirm before subscribing to heuristically-discovered feeds.

**Warning signs:**
- `discover <url>` returns empty list on sites known to have feeds
- User reports "I know this site has RSS but it wasn't found"

**Phase to address:**
- Phase that implements the discover command and fallback heuristics

---

### Pitfall 4: Relative Feed URLs in Autodiscovery Links

**What goes wrong:**
A website provides `<link href="/feed.xml">` (relative path) but the crawler doesn't resolve it correctly against the base URL, resulting in failed feed fetches.

**Why it happens:**
HTML5 allows relative URLs in `<link href>`. Some feed discovery implementations naively use `href` as-is without resolving it against the page's base URL. This is especially problematic for sites behind CDNs or with path-based subdirectories. The `<base href>` element can further complicate resolution.

**How to avoid:**
- Always resolve relative URLs using the page's URL as the base (Python: `urllib.parse.urljoin(page_url, href)`).
- Handle `<base href>` elements in the HTML body that override the document's base URL.
- Prefer absolute URLs in discovered feeds (log and prefer ones that are already absolute).

**Warning signs:**
- Discovered feed URLs that look like `/feed.xml`, `feed.xml`, `../feed.xml`
- "Failed to fetch feed" errors immediately after successful discovery

**Phase to address:**
- Phase that parses HTML `<head>` for `<link>` tags and resolves URLs

---

### Pitfall 5: Case-Sensitive Attribute Matching

**What goes wrong:**
Autodiscovery fails because the code checks for `type="application/rss+xml"` but the site serves `type="Application/Rss+Xml"` (uppercase) or uses non-standard casing.

**Why it happens:**
The RSS Board spec explicitly states attribute values must be lowercase, but real-world sites vary in casing. HTML parsers may normalize attribute values differently. feedparser's HTML parsing via BeautifulSoup may handle this differently than raw `re.findall()`.

**How to avoid:**
- **Normalize attribute values** to lowercase before matching: `type.lower()` and `rel.lower()`.
- Use a proper HTML parser (BeautifulSoup with lxml) rather than regex to find `<link>` elements in `<head>`.
- Match on `rel="alternate"` (case-insensitive) combined with `type` containing `rss`, `atom`, or `xml`.

**Warning signs:**
- Discovery works on some sites but not others with identical feed formats
- No pattern in feed URL itself — same feed URL works when entered manually

**Phase to address:**
- Phase that implements HTML link tag parsing for autodiscovery

---

### Pitfall 6: Bozo Feeds Corrupting Database State

**What goes wrong:**
feedparser's `bozo` flag is set on a malformed feed. The articles get stored with garbled titles, missing links, or broken pub_dates. Later queries fail or produce garbage output.

**Why it happens:**
feedparser has a "bozo" mechanism that parses malformed feeds anyway but marks them with `bozo=True` and stores the exception in `bozo_exception`. Common issues: malformed XML, bad character encoding (UTF-8 bytes in wrong encoding), timestamps in non-standard formats. The existing `parse_feed()` in rss_provider.py logs the bozo warning but still returns entries.

**How to avoid:**
- **Check `bozo` flag** on every feed parse. If `bozo=True`:
  - Log at WARNING level with the bozo_exception details
  - Optionally skip storing articles from bozo feeds (or store with an `is_bozo=True` flag)
  - During `feed add --discover`, reject feeds with bozo exceptions as "likely broken"
- Consider running feeds through an XML validator before storing if bozo rate is high.

**Warning signs:**
- `article list` shows entries with titles like `b'\xe2\x80\x9cSome Article Title\xe2\x80\x9d'` (UTF-8 bytes printed as repr)
- pub_date fields with partial timestamps or garbage strings

**Phase to address:**
- Phase that validates discovered feeds before subscribing

---

### Pitfall 7: Duplicate Feed Subscriptions

**What goes wrong:**
The same physical feed gets added multiple times under different URLs: `https://example.com/feed` and `https://example.com/feed/` (trailing slash difference), or `https://example.com/feed` vs `https://www.example.com/feed`.

**Why it happens:**
Websites often serve the same feed from multiple URLs: with/without trailing slash, with/without `www`, HTTP vs HTTPS, redirect chains. Auto-discovery picks up one variant; users manually add another; the crawler discovers a third via category page autodiscovery.

**How to avoid:**
- **Normalize feed URLs before storing**: strip trailing slashes, resolve `www` variants, follow one redirect and use the final URL.
- During `feed add`, check if a feed with the same normalized URL already exists.
- Store a `canonical_url` field in the database. When adding a new feed, compare against canonical URLs.
- Use URL normalization: `urllib.parse.urljoin` + strip trailing slash + lowercase scheme.

**Warning signs:**
- Duplicate entries in `feed list` for same content source
- `fetch --all` fetches the same articles multiple times (high duplicate count)

**Phase to address:**
- Phase that implements feed URL normalization in storage layer or provider

---

### Pitfall 8: Ignoring robots.txt During Discovery Crawls

**What goes wrong:**
The discovery crawler fetches pages that the site's `robots.txt` prohibits, resulting in 403s or potential IP blocks from aggressive hosting.

**Why it happens:**
The current system uses "robotexclusionrulesparser 1.7.1" with a "lazy mode" default of ignoring robots.txt. While acceptable for explicit feed URLs, auto-discovery crawls across multiple pages of a site and may hit disallowed paths (e.g., `/admin/`, `/private/`).

**How to avoid:**
- During autodiscovery crawls (fetching homepage to find `<link>` tags), **honor robots.txt** even if lazy mode is the default for explicit crawls.
- Parse `robots.txt` once per host and cache it; apply rules to each autodiscovery request.
- If a URL is disallowed by robots.txt, skip it but log the skip.

**Warning signs:**
- 403 errors clustered on specific paths during discovery
- Discovery succeeds but subsequent feed fetches get blocked (site added crawler to blocklist)

**Phase to address:**
- Phase that implements the multi-page discovery crawl logic

---

### Pitfall 9: Feed Type Coverage Gaps (CDF, RDF, Non-Standard Atom)

**What goes wrong:**
Auto-discovery finds a feed but feedparser fails to parse it, returning 0 entries silently, or the feed parses but articles have missing data (no link, no title).

**Why it happens:**
feedparser handles RSS 0.90-2.0, Atom 0.3/1.0 well, but CDF and RDF support is less robust. Additionally, some sites serve feeds with non-standard extensions (e.g., content encoded as CDATA in wrong places, Atom feeds with extension elements). The PROJECT.md explicitly lists "CDF, RDF" as required.

**How to avoid:**
- After parsing, **verify expected fields exist**: entries should have at minimum a `link` or `id` field.
- Log when feed type detected (feedparser's `feed.version`) does not match expected RSS/Atom types.
- Add validation that articles have `title` or `link` before storing — if neither exists, flag the feed as suspect.
- Test discovery against known CDF/RDF feeds (e.g., news sites that still use older formats).

**Warning signs:**
- Discovered feed returns 0 entries even though feed URL is valid when tested manually
- Articles stored with empty title and link fields
- feed.version detected as something unexpected (e.g., "cdf" vs "rss10")

**Phase to address:**
- Phase that implements feed validation after parsing

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip URL normalization on add | Simpler code | Duplicate feeds, duplicate articles | Never |
| Accept bozo feeds without flagging | Fewer "failed to add" errors | Garbage data in DB | Never — at minimum flag them |
| Regex-based `<link>` extraction | No dependency on HTML parser | Misses edge cases (quoted attributes, case variations) | Never |
| No depth limit on discovery crawl | Finds all feeds on site | Infinite loop, performance degradation | Never |
| Skip feed validation on `--discover` | Faster UX | User subscribes to dead feeds | Only with explicit user confirmation |
| Heuristic fallback unlimited attempts | Finds more feeds | Excessive HTTP requests, rate limiting | Never — cap at 3-5 patterns |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| feedparser + httpx | Assuming feedparser handles HTTP errors | httpx fetches content, feedparser only parses bytes |
| feedparser bozo flag | Treating bozo feeds as valid | Check `bozo=True` and log/flag the feed |
| BeautifulSoup + lxml | Forgetting lxml is not installed | Both are required per CLAUDE.md; add lxml to install deps |
| httpx + conditional requests | Sending ETag/Last-Modified to non-supporting servers | Check server response — 200 means server ignored conditional headers |
| asyncio + SQLite writes | Concurrent writes causing "database is locked" | Already solved via `asyncio.Lock + to_thread` — do not remove |
| Existing rate limiting (2s per-host) | Discovery not respecting crawl rate limits | Reuse existing rate limiter; discovery should be throttled |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded concurrent discovery | Mass HTTP requests to same host, 429 Too Many Requests | Respect existing 2s per-host rate limit; discovery is lower priority than feed refresh | At 10+ concurrent discovery requests to same domain |
| Large feed parsing in event loop | UI freezes during discovery | `feedparser.parse()` runs in `run_in_executor` (already implemented in crawl_async) | Large feeds (>1MB XML) block event loop if not in thread |
| Storing embeddings during discovery | Slow discovery completes, user waits | Defer embedding generation to background task or next fetch cycle | At 100+ discovered articles in single discovery run |
| No discovery result caching | Repeated `discover <url>` re-fetches everything | Cache discovered feeds per URL with TTL (e.g., 1 hour) | When user runs discover multiple times on same URL |
| Heuristic fallback on every discover | Multiple HTTP requests per failed discovery | Cache negative results (no feed found) per URL with TTL | When discover is run on 100s of URLs |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Following `javascript:` URLs in feed links | Feed links contain `javascript:void(0)` — crawler could "execute" if it evaluates them | Never evaluate discovered URLs as code; only accept `http://` and `https://` schemes |
| Fetching internal network URLs via redirect | Internal hostname leaks (e.g., `http://internal.corp.local/feed`) | Validate final URL is publicly reachable: check for private IP ranges, localhost |
| No size limit on downloaded feed | Large XML (e.g., 100MB) exhausts memory | Limit feed downloads to ~10MB; abort parse if content-length indicates larger |
| Storing untrusted feed content | XSS if feed HTML content is rendered unsanitized | Sanitize article content before storage or before display |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Auto-subscribing all discovered feeds | User gets spammed with unexpected content categories | Default `--automatic=off`: list feeds, let user confirm |
| No feedback during discovery | User waits 30+ seconds with no output, kills the command | Stream progress: "Checking example.com... Found 3 feeds" |
| Discovering 10+ feeds on one site | Overwhelming list for power users who only want main feed | Sort by "most items" or "main feed" heuristics; show count with "and N more" |
| No way to unsubscribe from auto-discovered sub-feeds | User stuck with category feeds they didn't intend | Allow `feed remove` to delete any feed regardless of source |
| No clear error when no feeds found | User doesn't know if tool works or site has no feed | Distinguish "no autodiscovery links found" vs "feeds found but all dead" |

---

## "Looks Done But Isn't" Checklist

- [ ] **Autodiscovery:** Often only handles `<link rel="alternate">` tags — verify it also handles non-standard variants (`rel="service.link"`, etc.)
- [ ] **Feed validation:** Often skips actual HTTP fetch during discovery — verify the discovered URL is actually fetchable and returns valid feed content
- [ ] **URL normalization:** Often missing — verify `https://example.com/feed` and `https://example.com/feed/` are treated as the same feed
- [ ] **Relative URL resolution:** Often done incorrectly — verify `/feed.xml` resolves to `https://example.com/feed.xml`
- [ ] **Feed type coverage:** Verify RSS 0.90, RSS 0.91, RSS 0.92, RSS 1.0, RSS 2.0, Atom 0.3, Atom 1.0, CDF, RDF all parse correctly
- [ ] **Bozo feed handling:** Verify bozo feeds are flagged in storage, not silently stored as normal
- [ ] **Infinite loop prevention:** Verify discovery terminates on sites with circular link patterns
- [ ] **Heuristic fallback:** Verify it actually finds feeds on sites that lack autodiscovery tags

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Infinite crawl loop | MEDIUM | Ctrl-C stops it; clear any partial state; add visited-set + depth-limit and retry |
| Dead feed subscription | LOW | `feed remove <feed_id>` deletes it; user re-adds manually if needed |
| Duplicate feeds | MEDIUM | Deduplicate in storage layer via normalized URL; migrate existing duplicates manually |
| Bozo feed in DB | HIGH | Add `is_bozo` flag via migration; re-fetch clean feeds for corrupted entries |
| Relative URL resolution failure | LOW | Fix URL resolution logic; re-run discovery on affected feeds |
| Heuristic hits rate limit | LOW | Wait for rate limit window; discovery is best-effort |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Infinite crawl loops | Discovery crawler with visited-set + depth-limit + timeout | Test with site that has circular links |
| Dead/empty feeds | Feed validation in `feed add --discover` before DB insert | Test with known-dead feed URL |
| Missing autodiscovery tags | Heuristic fallback (common feed URL patterns) | Test on 5-10 real sites known to lack autodiscovery |
| Relative feed URLs | URL resolution in HTML link parser | Test with sites using relative href in link tags |
| Case-sensitive attribute matching | BeautifulSoup parsing with lowercase normalization | Test with sites using uppercase attribute values |
| Bozo feeds corrupting DB | Check bozo flag before storing articles | Feed a malformed XML feed and verify it's flagged |
| Duplicate feed subscriptions | URL normalization on feed add | Add same feed via 3 different URL variants |
| Ignoring robots.txt | Honor robots.txt during autodiscovery crawl | Check robots.txt for site, verify disallowed paths are skipped |
| Unbounded concurrent discovery | Rate limiting (reuse existing 2s per-host limiter) | Run discover on 20 URLs simultaneously, verify no 429s |
| Feed type coverage gaps | Feed type validation + field presence checks | Test with CDF and RDF feeds specifically |

---

## Sources

- [RSS Board — RSS Autodiscovery](https://www.rssboard.org/rss-autodiscovery) (HIGH confidence — official spec)
- [feedparser Documentation — Advanced Features](https://feedparser.readthedocs.io/en/latest/advanced.html) (HIGH confidence — official docs)
- [feedparser README — Bozo Detection](https://pythonhosted.org/feedparser/) (MEDIUM confidence — official but brief)
- Project existing code: `src/providers/rss_provider.py` (lines 113-145 bozo handling, lines 29-67 httpx fetch), `src/application/fetch.py` (async concurrency), `src/providers/__init__.py` (provider discovery) (HIGH confidence)
- Project PROJECT.md: v1.9 milestone specification for "Automatic Discovery Feed" (HIGH confidence — project specification)

---
*Pitfalls research for: Automatic Discovery Feed (v1.9) — adding RSS/Atom/RDF auto-discovery to existing RSS reader CLI*
*Researched: 2026-03-27*
