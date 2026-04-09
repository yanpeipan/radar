---
status: awaiting_human_verify
trigger: "uv run feedship feed add https://www.youtube.com/feeds/videos.xml?channel_id=UCUl-s_Vp-Kkk_XVyDylNwLA fails with zsh: no matches found"
created: 2026-04-06T00:00:00Z
updated: 2026-04-06T00:00:00Z
---

## Current Focus
next_action: "Awaiting user confirmation that quoting the URL works"

## Symptoms
expected: feedship should add the YouTube RSS feed
actual: zsh reports "no matches found" before feedship even runs
errors:
  - "zsh: no matches found: https://www.youtube.com/feeds/videos.xml?channel_id=UCUl-s_Vp-Kkk_XVyDylNwLA"
reproduction: Run the command as-is in zsh shell without quoting the URL
started: Any time this URL is used unquoted in zsh

## Eliminated

## Evidence
- timestamp: 2026-04-06
  checked: feed.py CLI code
  found: feed_add command receives URL as click argument at line 98. No URL validation is performed - the URL is passed directly to discover_feeds().
  implication: The error occurs BEFORE feedship runs - it's a shell interpretation issue.

- timestamp: 2026-04-06
  checked: zsh glob behavior
  found: In zsh, `?` is a glob pattern matching any single character. When the unquoted URL with `?` is passed, zsh attempts to expand it as a file glob before feedship receives it.
  implication: This is zsh shell behavior, not a feedship bug.

- timestamp: 2026-04-06
  checked: cli-commands.md documentation
  found: No shell quoting guidance is provided for URLs containing special characters like `?`, `*`, `[`, `]`
  implication: Users are not warned about the need to quote URLs.

- timestamp: 2026-04-06
  checked: docs/cli-commands.md after fix
  found: Added Shell Quoting section with example showing correct quoting for YouTube URLs
  implication: Users will now be warned about quoting URLs with special characters.

## Resolution
root_cause: zsh glob expansion - The `?` character in the YouTube RSS URL is interpreted as a single-character glob pattern by zsh before the URL is passed to feedship. This happens at shell level, before feedship even runs.
fix: Add shell quoting guidance to docs/cli-commands.md in the feed add section, warning users to quote URLs containing special characters.
verification: "Added Shell Quoting section to docs/cli-commands.md with example showing correct quoting for YouTube URLs"
files_changed:
  - docs/cli-commands.md
