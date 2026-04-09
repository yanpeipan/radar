---
status: awaiting_human_verify
trigger: "feedship installed version cannot discover openai.com/news/rss.xml feed, shows 'No feeds discovered.'"
created: 2026-04-03T00:00:00Z
updated: 2026-04-03T00:00:00Z
---

## Current Focus
**Fix applied:** Added `patchright>=1.0.0` to cloudflare optional dependencies in pyproject.toml

**Self-verification:**
- .venv version (has patchright): Works - discovers 1 feed from openai.com/news/rss.xml
- UV tool version (lacks patchright): Still fails - "No feeds discovered."

**Next step:** User needs to reinstall UV tool to apply the fix

## Symptoms
expected: feedship feed add https://openai.com/news/rss.xml should discover and add the RSS feed
actual: Output "No feeds discovered."
errors: No other error messages (exception silently caught)
reproduction: Run feedship --debug feed add https://openai.com/news/rss.xml
timeline: Currently happening

## Eliminated
- hypothesis: "Source code missing the content-type check fix"
  evidence: "RSSProvider.match() has correct content-type check in both environments. Source code is identical."

- hypothesis: "Different scrapling versions"
  evidence: "Both environments have scrapling 0.4.3"

- hypothesis: "Different RSSProvider code"
  evidence: "Both use the same /Users/y3/feedship/src/providers/rss_provider.py"

## Evidence
- timestamp: 2026-04-03
  checked: "which feedship && feedship --version"
  found: "/Users/y3/.local/bin/feedship with version 1.4.0, uses /Users/y3/.local/share/uv/tools/feedship/bin/python"
  implication: "Installed version is a UV tool installation, not .venv"

- timestamp: 2026-04-03
  checked: "uv-receipt.toml for UV tool installation"
  found: "Installed with extras = ['ml', 'cloudflare'], python = '3.12'"
  implication: "Cloudflare extras were installed but missing patchright"

- timestamp: 2026-04-03
  checked: "patchright in UV tool vs .venv"
  found: "patchright NOT in UV tool (/Users/y3/.local/share/uv/tools/feedship/lib/python3.12/site-packages/), patchright IS in .venv"
  implication: "UV tool environment missing patchright"

- timestamp: 2026-04-03
  checked: "scrapling StealthyFetcher import"
  found: "ModuleNotFoundError: No module named 'patchright' when importing StealthyFetcher in UV tool Python"
  implication: "scrapling's stealth module requires patchright but it's not installed"

- timestamp: 2026-04-03
  checked: "async_fetch_with_fallback direct test in UV tool"
  found: "Exception: ModuleNotFoundError No module named 'patchright'"
  implication: "Basic Fetcher fails, fallback to StealthyFetcher fails due to missing patchright"

- timestamp: 2026-04-03
  checked: ".venv version test after fix"
  found: "Discovered 1 feed(s) from openai.com/news/rss.xml - works correctly"
  implication: "Fix works when patchright is available"

## Resolution
root_cause: "The cloudflare optional dependencies include 'playwright>=1.49.0' but NOT 'patchright'. However, scrapling's StealthyFetcher (used as fallback when basic Fetcher is blocked) imports 'from patchright.sync_api import sync_playwright'. When patchright is missing and basic Fetcher fails, the fallback raises ModuleNotFoundError which gets caught and returns None, causing 'No feeds discovered.'"
fix: "Added 'patchright>=1.0.0' to cloudflare optional dependencies in pyproject.toml"
verification: "Fix verified in .venv environment (which has patchright). UV tool environment needs reinstallation to apply fix."
files_changed: ["pyproject.toml"]
