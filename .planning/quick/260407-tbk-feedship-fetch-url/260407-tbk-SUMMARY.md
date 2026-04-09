# Quick Task 260407-tbk: feedship fetch --url E2E tests

**Completed:** 2026-04-07
**Commit:** c5a80e0
**Goal:** Add end-to-end tests for `feedship fetch --url` command

## What was done

Added 5 E2E tests in `tests/test_cli.py::TestFetchUrlCommands`:

1. **test_fetch_url_basic** — `fetch --url <url>` fetches articles and outputs success message
2. **test_fetch_url_json_output** — `fetch --url <url> --json` outputs valid JSON with `articles` and `count` fields
3. **test_fetch_url_no_articles** — empty provider returns "No articles found"
4. **test_fetch_url_no_provider** — unsupported URL returns exit code 1 with "No provider found"
5. **test_fetch_url_mutual_exclusion_with_id** — `--url` and `<id>` conflict returns exit code 1

## Key findings

- `match_first` is imported lazily inside `_do_fetch()` — mock at `src.providers.match_first` level
- Provider articles use `src.providers.base.Article` dataclass (not `src.models.Article`)
- `RSSProvider` is a catch-all fallback — force it to return None via `monkeypatch`

## Files changed

- `tests/test_cli.py` — added `TestFetchUrlCommands` class (+140 lines)
