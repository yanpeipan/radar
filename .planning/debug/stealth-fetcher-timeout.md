---
status: awaiting_human_verify
trigger: "StealthFetcher timeout 60s on nitter.net/elonmusk/rss, browser loads in 1-2s"
created: 2026-04-01T00:00:00Z
updated: 2026-04-01T00:00:00Z
---

## Current Focus
hypothesis: "network_idle: True in _STEALTH_SETTINGS causes Playwright to wait for all network connections to be idle, including blocked/slow external resources that never resolve"
test: "Check _wait_for_page_stability in scrapling/_base.py to confirm network_idle behavior"
expecting: "If network_idle waits for all external resources, disabling it should fix the timeout"
next_action: "Implement fix: set network_idle: False in _STEALTH_SETTINGS"

## Evidence
expected: StealthFetcher should load page in 2-5 seconds like a real browser
actual: StealthFetcher times out at 60 seconds
errors: "Page.goto: Timeout 60000ms exceeded" with "waiting until load"
reproduction: python -m src.cli fetch --all (NitterProvider falls back to StealthFetcher)
browser_access: 1-2 seconds (fast)
started: Unknown / investigating

## Eliminated
<!-- No hypotheses eliminated yet -->

## Evidence
- timestamp: 2026-04-01T00:00:00Z
  checked: Prior session notes
  found: "StealthFetcher doesn't use system proxy" - proxy fix was applied
  implication: "Proxy is not the cause of 60s timeout"

- timestamp: 2026-04-01T00:00:00Z
  checked: src/utils/scraping_utils.py lines 131-154
  found: "_STEALTH_TIMEOUT_MS = 30000 (30s) but user sees 60s timeout - scrapling default may override"
  implication: "scrapling's default timeout may be 60s, not 30s"

- timestamp: 2026-04-01T00:00:00Z
  checked: src/utils/scraping_utils.py lines 137-154
  found: "'network_idle': True in _STEALTH_SETTINGS - waits for network to be idle before returning"
  implication: "This could cause long waits if external resources (ads, analytics) are slow/blocked"

- timestamp: 2026-04-01T00:00:00Z
  checked: src/utils/scraping_utils.py line 153
  found: "'wait': 500 - waits 500ms after page load for JS to execute"
  implication: "Additional delay, but 500ms shouldn't cause 60s timeout"

- timestamp: 2026-04-01T00:00:00Z
  checked: scrapling/engines/_browsers/_base.py lines 141-146
  found: "_wait_for_page_stability calls page.wait_for_load_state('load') THEN waits for network_idle if enabled"
  implication: "network_idle=True forces waiting for ALL network connections to be idle, including blocked/external resources"

- timestamp: 2026-04-01T00:00:00Z
  checked: scrapling/engines/_browsers/_base.py line 137
  found: "_wait_for_networkidle uses page.wait_for_load_state('networkidle') which waits for no network activity for 500ms"
  implication: "If external resources (ads, tracking, fonts) are blocked by proxy or slow to resolve, networkidle never completes"

## Resolution
root_cause: "network_idle: True in _STEALTH_SETTINGS caused Playwright to wait for ALL network connections to be idle for 500ms. When external resources (ads, analytics, fonts) are blocked by proxy or slow to resolve, networkidle never completes, causing 60s timeout."
fix: "Changed network_idle: True to network_idle: False in _STEALTH_SETTINGS. Also reduced _STEALTH_TIMEOUT_MS from 30000 to 15000 since pages load faster without network_idle."
verification: "Test with: python -m src.cli fetch --all (NitterProvider should now use StealthFetcher and succeed within 15s)"
files_changed: [src/utils/scraping_utils.py]
