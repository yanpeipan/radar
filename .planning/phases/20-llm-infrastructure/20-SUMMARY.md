# Phase 20: LLM Infrastructure — Summary

**Completed:** 2026-04-08
**Goal:** LLM client is available and reliable for all downstream features

## What was done

### 1. Dependencies Added

- `litellm>=1.83.0` — unified LLM client (OpenAI/Ollama/Azure/Anthropic)
- `tiktoken>=0.8.0` — token counting for content truncation
- `pydantic-settings>=2.0.0` — config validation (was missing from deps)

### 2. `src/application/llm.py` (new file)

Core components:

- **`LLMConfig`** dataclass — loads from `config.yaml.llm` section
- **`LLMClient`** class — unified client with:
  - Provider fallback chain (primary → fallback chain)
  - `complete()` — async single prompt
  - `batch_complete()` — async batch with concurrency control
  - Semaphore-based max concurrency (default 5)
  - Timeout handling via `asyncio.wait_for`
- **`truncate_content()`** — tiktoken-based truncation at 8K tokens
- **`summarize_text()`, `score_quality()`, `extract_keywords()`** — convenience functions
- **`get_llm_client()`** — module-level singleton
- **`compute_content_hash()`** — SHA256 for deduplication

### 3. `src/application/config.py` extended

- Added `llm: dict` field to `FeedshipSettings`
- Default `llm:` section in `_create_default_config()`:
  - provider: openai, model: gpt-4o-mini
  - ollama_base_url: http://localhost:11434
  - fallback_chain: [openai, azure, anthropic]
  - max_concurrency: 5, timeout: 60s
  - max_tokens_per_call: 8000
  - daily_cap: 1000, weight_gate_min: 0.7

## Key Decisions

- LiteLLM as abstraction layer (not raw SDKs)
- Ollama health check at `http://localhost:11434` — fallback on ConnectionError
- tiktoken encoding fallback to `cl100k_base` for unknown models
- Singleton `get_llm_client()` for connection reuse

## Files Changed

- `pyproject.toml` — added litellm, tiktoken, pydantic-settings
- `src/application/llm.py` — new (340 lines)
- `src/application/config.py` — added llm config section
