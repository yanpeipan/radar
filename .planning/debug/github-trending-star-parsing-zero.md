---
status: awaiting_human_verify
trigger: "github-trending-star-parsing-zero: GitHub trending weekly fetch shows all repos with 0 stars ([0★]) instead of actual star counts"
created: 2026-04-05T00:00:00Z
updated: 2026-04-05T00:00:00Z
---

## Current Focus
hypothesis: TWO BUGS FOUND: (1) CSS selector uses nth-of-type(2) for stars but should be nth-of-type(1); (2) .text property doesn't get direct text nodes, must use ::text pseudo-element
test: Verified by fetching actual GitHub page and testing selectors
expecting: Fixing these bugs should restore star parsing
next_action: Apply fix to github_trending_provider.py

## Symptoms
expected: GitHub trending repos show actual star counts (e.g., "[15,000★] YC-backed project...")
actual: All repos show "[0★]" and "stars:0" in tags — star parsing is returning 0 for everything
errors: None (no errors, just wrong values)
reproduction: uv run feedship fetch --url 'https://github.com/trending?since=weekly' --json
started: After commit 61e5214 (260405-3sr)

## Eliminated

## Evidence
- timestamp: 2026-04-05T00:00:00Z
  checked: GitHub trending page structure
  found: |
    The HTML for stars/forks links is:
    <a href="/.../stargazers"><svg>...</svg> 18,828</a>
    The star count "18,828" is a DIRECT TEXT NODE after the SVG, not inside any child element.
  implication: scrapling's .text property returns empty string for these elements

- timestamp: 2026-04-05T00:00:00Z
  checked: CSS selector a.Link--muted:nth-of-type(2) vs actual structure
  found: |
    a.Link--muted:nth-of-type(1) = stars link (href ends with /stargazers)
    a.Link--muted:nth-of-type(2) = forks link (href ends with /forks)
    But TRENDING_SELECTORS has stars: a.Link--muted:nth-of-type(2) - WRONG!
  implication: The selector is selecting forks instead of stars

- timestamp: 2026-04-05T00:00:00Z
  checked: Text extraction method
  found: |
    el.text returns '' (empty string)
    el.css('::text').get() returns ' 18,828' (correct)
  implication: Must use ::text CSS pseudo-element to get direct text nodes

## Resolution
root_cause: |
  TWO BUGS:
  1. CSS selector "a.Link--muted:nth-of-type(2)" selects forks (2nd a.Link--muted), not stars (1st)
  2. Using .text property doesn't get direct text nodes - must use .css('::text').get() instead

  The combination of wrong selector + wrong text extraction method caused all stars to parse as 0.
fix: |
  1. Change stars selector from "a.Link--muted:nth-of-type(2)" to "a.Link--muted:nth-of-type(1)"
  2. Change forks selector from "a.Link--muted:nth-of-type(3)" to "a.Link--muted:nth-of-type(2)"
  3. Change el.text to el.css('::text').get() for both stars and forks text extraction
verification: Verified - fetch now shows "[18828★]", "[15383★]", "[36046★]" etc. with correct star counts in tags like "stars:18828"
files_changed:
- src/providers/github_trending_provider.py
