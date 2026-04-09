# Summary: AI Report 10-Iteration Evaluation & Optimization

**Date:** 2026-04-08
**Tasks Completed:** 5/5

## Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Retry logic + template fix | `7502b67` | `src/application/report.py` |
| 2 | EVALUATE_PROMPT JSON + evaluator fix | `b3c814c` | `src/llm/chains.py`, `src/llm/evaluator.py` |
| 4 | Remove improvement loop | `8a8c8d0` | `src/llm/evaluator.py`, `src/cli/report.py` |
| 5 | Classification prompt hints | `b3c814c` (with Task 2) | `src/llm/chains.py` |

Task 3 (template empty state) was included in commit `7502b67` along with Task 1 retry logic.

## Changes

### Task 1: Layer Summary Retry Logic
- `src/application/report.py` — `generate_cluster_summary()`
- Added 3-retry exponential backoff (2s, 4s, 8s) wrapping the LLM chain invocation
- After 3 failures, returns "（本周暂无重大进展）" instead of "（暂无总结）"
- Removed unused `time` import

### Task 2: Quality Evaluator Chain
- `src/llm/chains.py` — `EVALUATE_PROMPT` rewritten to return structured JSON: `{"coherence":0.0-1.0, "relevance":0.0-1.0, "depth":0.0-1.0, "structure":0.0-1.0}`
- `src/llm/evaluator.py` — `evaluate_report()` parse logic updated: scores divided by 4 (not 400), float values expected directly instead of 0-100

### Task 3: Template Empty State
- `src/application/report.py` — `_DEFAULT_TEMPLATE_MARKDOWN`
- Changed `{% if articles %}` to `{% if articles and summary and summary|trim %}` to hide sections with empty summaries
- Empty layers (no articles or no summary) now produce zero blank lines in output

### Task 4: Remove Improvement Loop
- `src/llm/evaluator.py` — Removed `run_improvement_loop()` function (~100 lines of dead code)
- `src/cli/report.py` — Removed `--run-improvement-loop` and `--iterations` CLI flags
- `ImprovementRecord` and `log_improvement()` kept for potential future use
- The loop produced identical output across iterations with no actual variation

### Task 5: Audit 芯片/能源 Empty Layers
- `src/llm/chains.py` — `CLASSIFY_PROMPT` updated with concrete examples
- 芯片: Added "e.g., NVIDIA Blackwell, Groq, Cerebras, TSMC, AMD GPU"
- 能源: Clarified "AI energy consumption, data center power, carbon footprint, renewable energy for AI"
- Root cause likely feed coverage gap (no subscribed feeds covering hardware/energy) — added hints to reduce misclassification into AI模型
