# Phase 23: Report Generation — Plan

**Phase:** 23
**Goal:** Users can generate structured daily reports from clustered articles using customizable Jinja2 templates
**Depends on:** Phase 22

## Task 1: Application Layer — Clustering Logic

**File:** `src/application/report.py` (new)

1. **`classify_article_layer(text, title) -> str`** — LLM classification into one of:
   - `AI应用` (Application)
   - `AI模型` (Model)
   - `AI基础设施` (Infrastructure)
   - `芯片` (Chip)
   - `能源` (Energy)

2. **`cluster_articles_for_report(article_ids) -> dict[str, list]`** — takes article IDs, fetches articles, classifies each into layer, groups by layer, generates per-layer summary

3. **`generate_report_sections(articles_by_layer, template_name) -> dict`** — renders template with articles grouped by layer

## Task 2: CLI Command — Report

**File:** `src/cli/report.py` (new)

```python
@cli.command("report")
@click.option("--template", default="default", help="Template name (default: 'default')")
@click.option("--since", required=True, help="Start date YYYY-MM-DD")
@click.option("--until", required=True, help="End date YYYY-MM-DD")
@click.option("--output", help="Save report to file")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--limit", default=200, help="Max articles to include")
@click.pass_context
def report(...)
```

- Fetches articles in date range using `list_articles_for_llm()`
- Runs classification + clustering via `cluster_articles_for_report()`
- Renders Jinja2 template
- `--output` saves to file; otherwise prints to console
- `--json` outputs machine-readable structured data

## Task 3: Default Template

**File:** `~/.config/feedship/templates/default.md` (created at runtime if missing)

Uses AI五层蛋糕 format from `skills/feedship-ai-daily/FINAL_FORMAT.md`.

## Task 4: Module Registration

**File:** `src/cli/__init__.py` — add `report` import

## Verify

```bash
uv run feedship report --help
uv run feedship report --since 2026-04-01 --until 2026-04-07 --json | head -50
```
