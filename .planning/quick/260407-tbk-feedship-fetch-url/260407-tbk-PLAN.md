---
name: "260407-tbk: feedship fetch --url E2E tests"
description: Add end-to-end tests for feedship fetch --url command
quick_id: 260407-tbk
slug: feedship-fetch-url
date: "2026-04-07"
mode: quick
---

## Plan

### Task 1: Add E2E tests for `feedship fetch --url`

**Files to create/modify:**
- `tests/test_cli.py` — add `TestFetchUrlCommands` class

**Action:**
Add 4 test cases to `TestFetchCommands` in `tests/test_cli.py`:

1. `test_fetch_url_basic` — `fetch --url <url>` returns articles successfully
2. `test_fetch_url_json_output` — `fetch --url <url> --json` outputs valid JSON with `articles` field
3. `test_fetch_url_no_provider` — `fetch --url <unsupported_url>` returns error
4. `test_fetch_url_mutual_exclusion` — `fetch --url <url> --id <id>` fails with mutual exclusion error

**Verify:**
- Run: `uv run pytest tests/test_cli.py::TestFetchUrlCommands -v`
- All 4 tests pass

**Done:**
- All 4 tests pass
- Committed with message: `test(fetch): add E2E tests for fetch --url`
