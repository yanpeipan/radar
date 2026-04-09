# Summary: 260409-qbr — 修复日报质量问题

## Template Fixes (committed to ~/.config/feedship/templates/)

### Issues Found in Report Output

**1. Missing article links**
- Old template used `s.url` but articles have `s.link`
- Fixed: Changed to `[{{ s.title }}]({{ s.link }})`

**2. Article truncation (aggregation incomplete)**
- Old template limited per-topic to `[:5]` articles
- Old template limited to `[:5]` topics per layer
- Fixed: Increased to `[:10]` per topic, no limit on topics per layer

**3. Signals section truncation**
- Old template limited to `[:10]` articles in signals
- Fixed: Increased to `[:20]`

## Root Cause of "No Translation"

MiniMax API cluster overloaded — all LLM calls return empty responses. This affects:
- Cluster classification → all fallback to "AI应用"
- Topic title generation → fallback to truncated article title
- Title translation → no translation because MiniMax is unreachable

Translation pipeline (`_translate_titles_batch_async`) also depends on MiniMax.

## Translation Logic (Correct by Design)

For `--language zh` reports:
- Source articles are English
- `format_title` filter only adds `(中文翻译)` for Chinese titles when target_lang != zh
- English → Chinese translation is NOT in scope (feed content is already in source language)
- This is correct behavior — translation is for non-Chinese readers reading zh reports

## What Still Needs MiniMax

| Feature | MiniMax Dependency |
|---------|-------------------|
| Cluster classification (五层) | REQUIRED (currently failing) |
| Topic title generation | REQUIRED (currently failing → fallback) |
| Title translation (zh→en) | REQUIRED (currently failing) |
| Layer summary generation | REQUIRED (currently not invoked) |

## Commits

- `5770d31` — handle empty MiniMax responses for titles/classification
- Template updated at `~/.config/feedship/templates/default.md` (not git-tracked)
