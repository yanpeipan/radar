# Phase 20: LLM Infrastructure — Plan

**Phase:** 20
**Goal:** LLM client is available and reliable for all downstream features
**Depends on:** None
**Requirements:** INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06

## Task 1: Create `src/application/llm.py` with LiteLLM integration

**File:** `src/application/llm.py` (new)

Create the LLM client module with:

1. **`LLMConfig` dataclass** — stores provider, model, api_key, base_url from dynaconf
2. **`get_llm_client()`** — returns configured LiteLLM client; supports: `openai`, `ollama`, `azure`, `anthropic`
3. **`ProviderChain`** — fallback chain: Ollama → OpenAI → Azure → Anthropic
4. **`LLMClient`** class wrapping LiteLLM with:
   - `complete(prompt, **kwargs)` → str
   - `batch_complete(prompts, **kwargs)` → list[str]
   - `async_complete_async()` variant with timeout
5. Health check: try Ollama at `http://localhost:11434`, catch ConnectionError, fall back

**Config in `config.yaml`** (new section):
```yaml
llm:
  provider: openai  # openai, ollama, azure, anthropic
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}  # from secrets
  ollama_base_url: http://localhost:11434
  fallback_chain:
    - openai
    - azure
    - anthropic
  max_concurrency: 5
  timeout_seconds: 60
```

## Task 2: Cost architecture

**File:** `src/application/llm.py` (same module)

1. **Feed weight gating** — decorator/context: `requires_weight(min_weight=0.7)` checks feed's weight before LLM call; skip if below threshold
2. **Recency gating** — `requires_recent(hours=48)` checks `published_at`; skip if older
3. **Deduplication** — compute `content_hash = sha256(title + content[:500])`; track in Redis or SQLite `llm_dedup` table; skip if hash seen <24h
4. **Hard daily cap** — counter in SQLite `llm_stats` table; increment on each LLM call; raise `DailyCapExceeded` if cap reached

## Task 3: Content truncation with tiktoken

**File:** `src/application/llm.py` (same module)

1. `truncate_content(content: str, max_tokens: int = 8000) -> tuple[str, bool]` — returns (truncated, was_truncated)
2. Use `tiktoken.encoding_for_model(model)` to count tokens
3. If content exceeds 8K tokens: truncate to 8K, set `was_truncated=True`
4. Log warning: `"Article {id} truncated: {original_tokens} → {truncated_tokens} tokens"`

## Task 4: Async wrapper with timeout and progress

**File:** `src/application/llm.py` (same module)

1. `async def llm_complete_async(prompt: str, **kwargs) -> str` — wraps LiteLLM `acompletion` with `asyncio.timeout()`
2. `async def batch_complete_async(prompts: list[str], max_concurrency: int = 5) -> list[str]` — uses `asyncio.Semaphore` for concurrency control
3. `RateLimiter` class — `max_retries=3`, exponential backoff on 429/500 errors

## Task 5: Unit tests

**File:** `tests/test_llm.py` (new)

1. `test_llm_config_parsing` — verify config loads correctly
2. `test_provider_fallback_chain` — mock Ollama down, verify fallback to OpenAI
3. `test_truncate_content` — verify truncation at 8K tokens, flag set correctly
4. `test_weight_gating` — mock feed with weight=0.5, verify skip
5. `test_concurrency_limit` — verify max 5 concurrent calls

## Verify

- Run: `uv run pytest tests/test_llm.py -v`
- All 5 tests pass
- Run: `uv run feedship --help` (no-op, verify import works)
