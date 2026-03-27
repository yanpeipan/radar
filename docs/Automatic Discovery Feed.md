# Automatic Discovery Feed

## CLI Commands

- `discover <url> --discover-deep [n]` - Discover feeds from a website URL without subscribing
- `feed add <url> --discover [on/off] --automatic [on/off] --discover-deep [n]` - Add a feed with optional auto-discovery

## Discovery Algorithm

### Depth=1 (Single Page)

1. Fetch page HTML from URL
2. Parse `<head>` for `<link rel="alternate" type="...">` tags (DISC-01)
3. If found, validate each feed URL via HEAD request
4. If not found, probe well-known paths: /feed, /feed/, /rss, /rss.xml, /atom.xml, /feed.xml, /index.xml (DISC-02)
5. Validate discovered feeds

### Depth > 1 (BFS Deep Crawl) (DISC-07)

1. Start BFS from initial URL at depth=1
2. Maintain visited-set of normalized URLs to avoid cycles
3. For each page at depth < max_depth:
   a. Check robots.txt if depth > 1 (DISC-08)
   b. Respect rate limiting: 2 seconds per host
   c. Parse HTML, extract internal links
   d. Add unvisited links to queue with depth+1
   e. Discover feeds on current page
4. Return all discovered feeds

## URL Resolution Rules (DISC-03)

- Relative URLs resolved via `urllib.parse.urljoin()`
- `<base href>` in `<head>` overrides base URL
- Fragment identifiers (#...) stripped for visited-set

## Supported Feed Types

- RSS 2.0: `application/rss+xml`
- Atom 1.0: `application/atom+xml`
- RDF: `application/rdf+xml`
- Also accepted: `application/xml`, `text/xml`

## Rate Limiting

- 2 second delay between requests to same host
- Implemented via per-host request timestamp tracking
- Applies only to deep crawl (depth > 1)

## robots.txt Compliance (DISC-08)

- Uses `robotexclusionrulesparser` library
- Only enforced when depth > 1 (depth=1 is like normal browser)
- If no robots.txt exists, crawling is allowed
- Uses `User-Agent: *` for robots.txt checks

## Well-Known Paths (DISC-02)

Probed in order if no autodiscovery tags found:

1. /feed
2. /feed/
3. /rss
4. /rss.xml
5. /atom.xml
6. /feed.xml
7. /index.xml
