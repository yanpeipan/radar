# 260408-l0b Summary: LCEL Chains Wired Into Report Generation

## Tasks Completed

### Task 1: AsyncLLMWrapper in chains.py
- Created `class AsyncLLMWrapper(Runnable)` that delegates to `LLMClient.complete()`
- Provides provider fallback + rate-limiting for all LCEL chains
- Singleton pattern via `_get_llm_wrapper()`
- Replaced `_get_model()` pattern (which bypassed LLMClient) in all three chain factories:
  - `get_classify_chain()` → `CLASSIFY_PROMPT | _get_llm_wrapper() | StrOutputParser()`
  - `get_layer_summary_chain()` → `LAYER_SUMMARY_PROMPT | _get_llm_wrapper() | StrOutputParser()`
  - `get_evaluate_chain()` → `EVALUATE_PROMPT | _get_llm_wrapper() | StrOutputParser()`

### Task 2: Chains wired into report.py
- `classify_article_layer()` now calls `get_classify_chain().ainvoke({"title": title, "content": sample})` instead of `llm_complete()`
- `generate_cluster_summary()` now calls `get_layer_summary_chain().ainvoke({"layer": layer, "article_list": article_list})` instead of `llm_complete()`
- Output format unchanged (category name, summary text)
- Removed unused `llm_complete` import from report.py

### Task 3: Duplicate prompts removed
- Inline prompts removed from `report.py` (now centralized in chains.py)
- `get_evaluate_chain()` verified as already wired to `evaluator.py` — no cleanup needed there
- No duplicate prompt strings across both files

## Files Changed
- `src/llm/chains.py` (+54/-28 lines)
- `src/application/report.py` (+7/-24 lines)

## Commit
`4630503 refactor(llm): wire LCEL chains into report generation`
