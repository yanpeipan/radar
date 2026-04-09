# Research: 去掉所有v2

## References Found

All `cluster_articles_for_report_v2` and `render_report_v2` references:

### src/application/report.py
- Line 452: Comment mentioning `render_report_v2`
- Line 816: `def cluster_articles_for_report_v2(...)` — **definition**
- Line 841: `async def render_report_v2(...)` — **definition**
- Line 849: Comment referencing `cluster_articles_for_report_v2()`

### src/cli/report.py
- Line 15-16: `from src.application.report import cluster_articles_for_report_v2, render_report_v2`
- Line 71: `data = cluster_articles_for_report_v2(...)`
- Line 112: `render_report_v2(data, ...)`

### src/llm/evaluator.py
- Line 301: `from src.application.report import cluster_articles_for_report_v2, render_report_v2`
- Line 306: `data = cluster_articles_for_report_v2(...)`
- Line 309: `report_text = asyncio.run(render_report_v2(data))`

### tests/test_report.py
- Line 397: `"src.cli.report.cluster_articles_for_report_v2"` (monkeypatch)
- Line 427-428: docstring and import of `cluster_articles_for_report_v2`
- Line 440: `data = cluster_articles_for_report_v2(...)`

## Approach

Rename in-place across all files using `replace_all`:

1. `cluster_articles_for_report_v2` → `cluster_articles_for_report`
2. `render_report_v2` → `render_report`
3. `_cluster_articles_v2_async` → `_cluster_articles_async` (internal function)

## Risks

- No external API consumers (pure internal refactor)
- All changes are in owned codebase
- No database migrations needed
- CLI command name unchanged (`report`)

## Verification Plan

After rename:
```bash
grep -rn "cluster_articles_for_report_v2\|render_report_v2" src tests
```
Should return zero results.

```bash
grep -rn "cluster_articles_for_report[^_]\|render_report[^_]" src tests
```
Should show all renamed references.
