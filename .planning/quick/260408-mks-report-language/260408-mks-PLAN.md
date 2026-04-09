---
must_haves:
  - "--language flag added to report CLI (choices: zh, en, ja, ko, default: zh)"
  - "translate_report() function that skips translation when language is zh"
  - "Article titles/links preserved in original language during translation"
---

## Plan: Report Language Translation Pipeline

### Context
The report generation pipeline produces Chinese output. User wants `--language` flag to generate reports in en, ja, ko. Research recommends post-rendering translation (Option B) to avoid database pollution and minimize LLM calls.

### Task 1: Add Translation Chain to chains.py
**Files:** `src/llm/chains.py`
**Action:** Add `TRANSLATE_PROMPT` and `get_translate_chain()` using existing LCEL pattern
**Verify:** Import and call `get_translate_chain()` works without error
**Done:** ☐

### Task 2: Add translate_report() to report.py
**Files:** `src/application/report.py`
**Action:** Add `translate_report()` async function that:
- Returns original text immediately if `target_lang == "zh"`
- Translates section headers and body text
- Preserves article bullet points (lines with `](` link pattern)
**Verify:** `translate_report("test", "zh")` returns "test", non-zh triggers chain
**Done:** ☐

### Task 3: Wire --language Flag in CLI
**Files:** `src/cli/report.py`
**Action:** Add `--language` option (choices: zh/en/ja/ko, default: zh), call `translate_report()` after `render_report()` when language != zh
**Verify:** `feedship report --language en --since X --until Y` produces translated output
**Done:** ☐

---

## Verification Commands
```bash
# Test chain import
python -c "from src.llm.chains import get_translate_chain; print('OK')"

# Test translate_report zh skip
python -c "from src.application.report import translate_report; import asyncio; print(asyncio.run(translate_report('hello', 'zh')))"

# Full CLI test (requires real data)
feedship report --language en --since 2026-04-01 --until 2026-04-07
```
