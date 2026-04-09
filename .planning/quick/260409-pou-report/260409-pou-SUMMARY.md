# Summary: 260409-pou — 运行report命令、解决异常、评估新闻质量

## Issues Found & Fixed

### 1. litellm 1.83.0 Model Pricing Exception
**Problem:** litellm 1.83.0 enforces strict model pricing validation. MiniMax/M2.7 not in litellm's model cost map → cost calculation raises `Exception: model not mapped`.

**Fix:** Added `litellm.register_model()` at module load time in `src/llm/core.py` with zero-cost pricing for `minimax/MiniMax-M2.7`.

### 2. MiniMax Thinking Block Injection
**Problem:** MiniMax returns `<think>...</think>` XML tags in responses, breaking classification parsing. The `classify_cluster_layer` function saw empty result after tag stripping.

**Fix:** Added `re.sub(r"<[^>]+>", "", result)` before category matching in both `classify_article_layer` and `classify_cluster_layer`.

### 3. `default.md` Template Using Old v1 Variables
**Problem:** CLI calls `render_report(template_name="default")` but `default.md` referenced undefined v1 variables (`articles_by_layer`, `layer_summaries`).

**Fix:** Rewrote `default.md` to use v2 data structure (`layers`, `signals`, `creation`).

## Verification

- 15/15 tests pass
- Pre-commit clean
- All 3 fixes committed

## Files Changed

- `src/llm/core.py` — model pricing registration
- `src/application/report.py` — thinking block stripping
- `~/.config/feedship/templates/default.md` — template rewrite

## Commit

`e1c7da5` — fix(report): litellm model pricing + MiniMax thinking blocks + template
