---
status: resolved
trigger: "python -m src.cli crawl https://www.qbitai.com/feed returns 403 Forbidden"
created: 2026-03-23T12:00:00Z
updated: 2026-03-23T12:05:00Z
---

## Current Focus
hypothesis: "403 error caused by missing/bot User-Agent header in httpx request"
test: "Tested qbitai.com/feed with different User-Agents using curl"
expecting: "If site blocks bot UAs, browser UA should work and httpx default should fail"
next_action: "CONFIRMED - root cause found. Document fix recommendation."

## Symptoms
expected: "Feed content should be fetched successfully"
actual: "Client error '403 Forbidden' for url 'https://www.qbitai.com/feed'"
errors:
  - "Client error '403 Forbidden' for url 'https://www.qbitai.com/feed'"
reproduction: "python -m src.cli crawl https://www.qbitai.com/feed"
started: "2026-03-23"

## Eliminated

## Evidence
- timestamp: 2026-03-23T12:01:00Z
  checked: "src/crawl.py HTTP client configuration"
  found: "Line 125: httpx.get(robots_check_url, timeout=30.0, follow_redirects=True) - NO custom headers set"
  implication: "httpx default User-Agent is 'python-httpx/<version>' which is identified as bot"

- timestamp: 2026-03-23T12:04:00Z
  checked: "Tested qbitai.com/feed with different User-Agents using curl"
  found: |
    Browser UA (Chrome/Mac): HTTP/1.1 200 OK
    Default curl UA: HTTP/1.1 403 Forbidden
    python-httpx UA: HTTP/1.1 403 Forbidden
  implication: "CONFIRMED - site blocks bot-like User-Agent strings"

## Resolution
root_cause: "httpx.get() in src/crawl.py uses default User-Agent 'python-httpx/<version>' which qbitai.com blocks with 403"
fix: "Add browser-like User-Agent header to httpx requests in src/crawl.py"
verification: ""
files_changed: []
