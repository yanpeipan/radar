# Quick Task: LCEL Chains Integration for Report Generation

**Researched:** 2026-04-08
**Domain:** LangChain LCEL integration with existing LLMClient
**Confidence:** MEDIUM

## Summary

The existing `chains.py` LCEL chains (`get_classify_chain()`, `get_layer_summary_chain()`) are **not wired into** `report.py`. Instead, `report.py` constructs prompts inline and calls `llm_complete()` directly. The chains use `litellm.ainvoke` directly, bypassing `LLMClient` fallback/rate-limit features. Wiring chains in requires either (a) making `LLMClient` Runnable via `RunnableLambda`, or (b) accepting dual paths.

**Primary recommendation:** Wrap `LLMClient.complete` as `RunnableLambda` so chains can use LLMClient with its fallback/rate-limit intact.

---

## 1. Architecture Issue: Dual Code Paths

### Current State

| Component | Invocation | LLMClient Used? |
|-----------|------------|-----------------|
| `chains.py` `_get_model()` | `litellm.ainvoke(model_name, prompt)` | NO - direct litellm |
| `report.py` `classify_article_layer()` | `llm_complete(prompt, ...)` | YES - via LLMClient |
| `report.py` `generate_cluster_summary()` | `llm_complete(prompt, ...)` | YES - via LLMClient |

**Problem:** `chains.py` chains miss LLMClient features:
- Provider fallback chain (Ollama -> OpenAI -> Azure -> Anthropic)
- Semaphore-based concurrency control
- Daily call cap tracking
- Rate limiting with exponential backoff

**Evidence:** `chains.py` line 13-17 - `_get_model()` returns a lambda calling `litellm.ainvoke` directly.

---

## 2. How to Wire Chains Into `classify_article_layer` and `generate_cluster_summary`

### Option A: RunnableLambda Wrap (Recommended)

```python
# In core.py or chains.py
from langchain_core.runnables import RunnableLambda

def _llm_client_runnable(prompt: str) -> str:
    """Run LLMClient synchronously (for LCEL invoke)."""
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        get_llm_client().complete(prompt)
    )

llm_runnable = RunnableLambda(_llm_client_runnable)
```

Then in `get_classify_chain()`:
```python
from langchain_core.runnables import RunnableLambda
from src.llm.core import get_llm_client

def _make_async_complete():
    async def _complete(prompt: str) -> str:
        return await get_llm_client().complete(prompt)
    return RunnableLambda(lambda x: x)  # placeholder - see below

# Better: use ainvoke with RunnableLambda
async def _llm_async_complete(prompt: str) -> str:
    return await get_llm_client().complete(prompt)

# In chain factory:
def get_classify_chain():
    return CLASSIFY_PROMPT | RunnableLambda(lambda x: asyncio.run(_llm_async_complete(x["content"])))
```

**Problem:** `RunnableLambda` is sync-first; async LCEL chains need `ainvoke`. The cleanest path is `ChatPromptTemplate | _AsyncLLMWrapper() | StrOutputParser()`.

### Option B: Create AsyncLLMWrapper Class

```python
# In chains.py
from langchain_core.runnables import Runnable
from src.llm.core import get_llm_client

class AsyncLLMWrapper(Runnable):
    """Wraps LLMClient to be LCEL-compatible."""

    def invoke(self, input: str | dict, config=None) -> str:
        # Sync fallback - use for .pipe() sync composition
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(self._ainvoke(input))

    async def _ainvoke(self, input: str | dict) -> str:
        if isinstance(input, dict):
            prompt = input.get("title", "") + "\n" + input.get("content", "")
        else:
            prompt = input
        return await get_llm_client().complete(prompt)

    async def ainvoke(self, input: str | dict, config=None) -> str:
        return await self._ainvoke(input)

# Usage:
def get_classify_chain():
    return CLASSIFY_PROMPT | AsyncLLMWrapper() | StrOutputParser()
```

This is the cleanest approach - a proper `Runnable` class that delegates to `LLMClient.complete()`.

---

## 3. Should `chains.py` Use LLMClient Instead of `litellm.ainvoke`?

**Yes, but only if the chains are wired in.** As-is, `chains.py` is dead code that bypasses LLMClient's resilience features.

**Trade-off:**
- `litellm.ainvoke` handles retries (max_retries=3) and timeouts natively
- `LLMClient` adds provider fallback chain + semaphore concurrency + daily cap
-两者叠加会导致双重重试和潜在的速率限制冲突

**Recommendation:** If wiring chains into report.py, replace `_get_model()` with a `RunnableLambda`/`Runnable` that calls `LLMClient.complete()`. Remove the `max_retries` in `_get_litellm_kwargs` when going through LLMClient since LLMClient handles provider failover already.

---

## 4. Should LLMClient Be Made Runnable (LCEL Compatible)?

**Yes, with caveats.** The `Runnable` interface requires implementing `invoke`, `ainvoke`, `batch`, `abatch`. The main challenge is `ainvoke` returning `str` while standard LCEL expects `AIMessage`.

**Minimal approach: Not full Runnable, just RunnableLambda factory**

Instead of making `LLMClient` implement `Runnable`, expose a helper:

```python
# In core.py
from langchain_core.runnables import RunnableLambda

def llm_as_runnable(max_tokens: int = 300, temperature: float = 0.3):
    """Factory: returns a RunnableLambda backed by LLMClient."""
    async def _run(input: dict) -> str:
        client = get_llm_client()
        # Support both string and dict input
        if isinstance(input, str):
            prompt = input
        else:
            # Chain input dict - construct prompt from fields
            prompt = input.get("prompt") or str(input)
        return await client.complete(prompt, max_tokens=max_tokens, temperature=temperature)
    return RunnableLambda(_run)
```

This is simpler than implementing full `Runnable` and works for `|` composition.

---

## 5. Integration Risks

### Risk 1: Chains Not Wired = Dead Code
The existing `chains.py` functions (`get_classify_chain()`, `get_layer_summary_chain()`) are **never called** from `report.py`. They exist but aren't used.

**Mitigation:** Decide whether to (a) wire them in, or (b) remove them. Don't leave dead code that implies functionality.

### Risk 2: Duplicate Retry Logic
`LLMClient` sets `max_retries=3` in `_get_litellm_kwargs()`. LiteLLM also retries internally. With dual-path chains (chains.py using litellm.ainvoke directly while report.py uses LLMClient), retries may fire twice for the same failure.

**Mitigation:** When wiring chains via LLMClient, ensure `max_retries=0` in the litellm kwargs so LLMClient's provider-fallback loop handles retries.

### Risk 3: Concurrency Mismatch
`LLMClient` uses `asyncio.Semaphore` for concurrency control. If chains.py is used directly via `ainvoke`, that semaphore is bypassed, potentially overwhelming the API.

**Mitigation:** All LLM calls go through LLMClient. Chain factories should not create their own litellm clients.

### Risk 4: Input Format Mismatch
`classify_article_layer()` takes `(text, title)` as positional args. The LCEL chain expects `{"title": ..., "content": ...}`. Refactoring needed to pass dict inputs through the chain.

**Mitigation:** Create thin wrapper functions that extract args and pass as dict:

```python
async def classify_via_chain(title: str, text: str) -> str:
    chain = get_classify_chain()
    result = await chain.ainvoke({"title": title, "content": text[:2000]})
    return result
```

---

## 6. Actionable Integration Steps

1. **Remove or wire `chains.py`**: Either wire into `report.py` or delete. Don't leave orphaned LCEL chains.

2. **Create `AsyncLLMWrapper` Runnable class** (if wiring):
   - Implements `Runnable` interface
   - Delegates to `LLMClient.complete()`
   - Used in chain factories instead of raw litellm.ainvoke

3. **Refactor `report.py` callers**:
   - `classify_article_layer`: call `get_classify_chain().ainvoke({"title": title, "content": text[:2000]})`
   - `generate_cluster_summary`: call `get_layer_summary_chain().ainvoke({"layer": layer, "article_list": article_list})`

4. **Disable litellm internal retries** when using LLMClient path:
   - Set `max_retries=0` in `_get_litellm_kwargs()` when called via LLMClient fallback loop

5. **Keep existing `llm_complete()` for ad-hoc use** in report.py:
   - Some callers just need a simple string prompt
   - No need to force everything through LCEL

---

## Open Questions

1. **Should chains.py be the single entry point for all LLM calls in report generation?**
   - Pro: Unified, testable, composable
   - Con: Requires refactoring `report.py` call sites
   - Recommendation: Yes, but only after LLMClient is Runnable-compatible

2. **What about `get_evaluate_chain()`?** Currently unused. Should it be wired into report generation for quality scoring, or removed?

---

## Sources

- `src/llm/chains.py` - existing LCEL chains (lines 1-96)
- `src/llm/core.py` - LLMClient (lines 198-331), `_get_litellm_kwargs` (lines 213-237)
- `src/application/report.py` - `classify_article_layer` (lines 30-68), `generate_cluster_summary` (lines 71-106)
- LangChain Runnable interface: `langchain_core.runnables.Runnable`
