# Project Research Summary

**Project:** Feedship v1.11 LLM 智能报告
**Domain:** Python CLI RSS reader with LLM-powered article analysis
**Researched:** 2026-04-07
**Confidence:** MEDIUM

## Executive Summary

Feedship v1.11 adds LLM capabilities to a Python CLI RSS reader for article summarization, quality scoring, keyword extraction, topic clustering, and daily digest report generation. Experts recommend LiteLLM (1.83.x) as the unified LLM client with support for OpenAI, Ollama, Azure, and Anthropic providers. Storage extends existing SQLite (with new article fields) and ChromaDB (with new collections for summaries and keywords). The build follows a 5-phase dependency order: LLM client first, then storage, then CLI commands, then trigger integration, then advanced features.

The fundamental challenge is scale: 110 feeds with 50+ articles each creates thousands of potential LLM calls per fetch cycle. Cost control through feed weighting, deduplication, and caching is not optional - it is the architecture. Three trigger patterns (inline during fetch, on-demand CLI, scheduled via OpenClaw) require different async handling strategies. The "AI Five-Layer Cake" taxonomy (Application/Model/Infrastructure/Chip/Energy) provides a content organization framework for daily reports.

Key risks include API cost blowup (P0), rate limiting (P0), and template injection (P0). Most pitfalls are preventable with standard patterns (caching, retries, fallbacks, sandboxing) but require deliberate architectural decisions in Phase 1.

## Key Findings

### Recommended Stack

**Core technologies:**

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **litellm** | 1.83.x | Unified LLM client | Single API for 100+ providers, built-in retries, streaming, cost tracking |
| **openai** | 2.30.x | OpenAI SDK | LiteLLM dependency; direct use for advanced features |
| **anthropic** | 0.89.x | Anthropic SDK | Claude support when not going through LiteLLM |
| **jinja2** | - | Template engine | Report generation with user templates |
| **tiktoken** | - | Token counting | Content truncation before LLM calls |

**Already present (no change needed):**
- chromadb 1.5.x (ml extras) - new collections for summaries/keywords
- sentence-transformers 3.0.x - embedding-based clustering
- trafilatura 1.0.x - full-text content extraction
- pydantic, pydantic-settings - config extension

**NOT adding:** LangChain, LlamaIndex, Instructor, Guidance, textblob, spacy

### Expected Features

**Must have (table stakes):**
- Single-article summarization (3-5 sentences, cacheable)
- Quality scoring (0.0-1.0 float, JSON output with breakdown)
- SQLite persistence for LLM results (summary, quality_score, keywords, tags, summarized_at)
- CLI commands: `feedship summarize`, `feedship report`

**Should have (competitive):**
- Multi-article aggregated summaries per topic cluster
- Topic clustering using hybrid embedding + LLM classification
- Provider fallback chain (Ollama -> OpenAI -> Azure -> Anthropic)
- Batch processing with progress bars and rate limiting

**Defer (v2+):**
- Personalized ranking using LLM scores
- Export to Obsidian/Notion
- Advanced topic trend analysis over time

### Architecture Approach

LLM features integrate via a new `src/application/llm.py` module with four core functions: `summarize_article()`, `score_quality()`, `extract_keywords()`, and `generate_report()`. Storage extends SQLite with ALTER TABLE migrations adding 5 new columns, and ChromaDB with separate collections for summary embeddings and keyword embeddings. Three trigger patterns: (1) inline during fetch for high-weight feeds using `asyncio.create_task()`, (2) on-demand via `summarize` CLI command, (3) scheduled via OpenClaw cron integration for daily reports.

**Major components:**
1. **LLM Client Module** (`src/application/llm.py`) - Provider abstraction, prompt management, caching logic
2. **Storage Layer** - SQLite schema migration, new queries, ChromaDB collection management
3. **CLI Commands** - `summarize` and `report` commands with progress reporting
4. **Template System** - Jinja2 templates in `~/.config/feedship/templates/` with sandboxed rendering
5. **Trigger Integration** - Async task queuing, provider fallback, rate limiting

### Critical Pitfalls

1. **API Cost Blowup** — 110 feeds x 50 articles x 5 features = 27,500 LLM calls per cycle. Prevention: feed weight gating (only process weight >= 0.7), recency gating (last 24-48h), deduplication via content hash, batch calls, hard daily cap.

2. **Rate Limiting** — 429 errors cascade without retry logic. Prevention: LiteLLM with `max_retries=3`, exponential backoff, circuit breaker pattern, controlled concurrency (max 5 concurrent), per-provider rate limit awareness.

3. **Template Injection** — Malicious content in Jinja2 template evaluation. Prevention: Sandboxed Jinja2 environment, autoescape enabled, whitelist filters only, no eval(), user template warnings.

4. **Offline Ollama** — Local provider failure breaks entire LLM feature set. Prevention: Provider fallback chain, health check on startup, automatic cloud fallback, `--force-provider` flag override.

5. **Content Truncation** — Long articles lose key points at end. Prevention: Token counting with tiktoken, truncation strategy (first 60% + last 20%), content warning for >10K tokens, section-aware extraction.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Core LLM Infrastructure
**Rationale:** All other components depend on LLM client. Most critical pitfalls (cost, rate limiting, deduplication, provider fallback) must be addressed here before any feature work.

**Delivers:**
- `src/application/llm.py` with LiteLLM integration
- Provider fallback chain (Ollama -> OpenAI -> Azure -> Anthropic)
- Cost architecture: feed weight gating, recency gating, deduplication
- Content truncation with tiktoken
- Async wrapper with timeout handling

**Addresses:** Pitfalls #1, #2, #4, #5, #7 (Cost Blowup, Rate Limiting, Offline Ollama, Content Truncation, Duplicate Summarization)

**Avoids:** Building features on broken cost/rate-limit foundation

### Phase 2: Storage Extension
**Rationale:** LLM results need persistent storage. Schema changes and new queries must exist before CLI commands can be implemented.

**Delivers:**
- SQLite schema migration (ALTER TABLE articles ADD COLUMN summary, quality_score, keywords, tags, summarized_at)
- Storage functions: `update_article_llm()`, `get_article_with_llm()`, `list_articles_for_llm()`
- ChromaDB collections: `article_summaries`, `article_keywords` with collection registry
- Unit tests for storage layer

**Uses:** Stack: litellm, chromadb extensions
**Implements:** Architecture: Storage Layer

**Avoids:** ChromaDB collection conflicts (Pitfall #9)

### Phase 3: CLI Commands
**Rationale:** User-facing interface. Depends on Phase 1 (LLM client) and Phase 2 (storage). Should be tested end-to-end before trigger integration.

**Delivers:**
- `feedship summarize` command (single article, --all batch, --feed-id, --force, --json)
- `feedship report` command (--template, --date, --output, --json)
- Progress bars with rich.Progress
- Integration tests

**Uses:** Stack: jinja2, click, rich
**Implements:** Architecture: CLI Commands

### Phase 4: Trigger Integration
**Rationale:** Automatic LLM processing during fetch cycle. Depends on all components working. Templates are data, created here.

**Delivers:**
- Inline LLM processing for high-weight feeds (asyncio.create_task queue)
- Report template files in `~/.config/feedship/templates/` (default.md, brief.md)
- config.yaml LLM section
- OpenClaw cron integration for daily digest
- User documentation: docs/llm-features.md

**Uses:** Architecture: Trigger Integration patterns
**Implements:** AI Five-Layer Cake taxonomy

**Research Flags:** OpenClaw integration details may need deeper research if not already documented.

### Phase 5: Advanced Features
**Rationale:** Nice-to-have features that depend on everything else working. Address hallucination quality assurance and topic clustering refinement.

**Delivers:**
- Hybrid topic clustering (embedding + LLM classification)
- Chain-of-thought quality prompting with confidence scores
- Self-verification prompts
- Topic trend analysis over time

**Uses:** Architecture: Advanced patterns
**Avoids:** Hallucination (Pitfall #3)

**Research Flags:** Topic clustering algorithm fine-tuning may need validation against actual article content patterns.

### Phase Ordering Rationale

1. **LLM client first** — All other components depend on provider abstraction; cost/rate-limit foundation prevents 10x-100x cost increase
2. **Storage second** — CLI and fetch depend on data schema; migration must precede queries
3. **CLI third** — User-facing; depends on storage + LLM working; testable in isolation
4. **Triggers fourth** — Depends on all pieces; templates are data (created here)
5. **Advanced fifth** — Depends on everything; nice-to-have, not blocking

**Grouping rationale:** Features that share dependencies are in same phase. Anti-patterns to avoid: LLM calls in hot path, no cache invalidation, large batch without backpressure, raw LLM output without validation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | LiteLLM, OpenAI, Anthropic verified on PyPI; versions confirmed |
| Features | MEDIUM | Established LLM patterns; "AI Five-Layer Cake" from existing skill |
| Architecture | MEDIUM | Follows existing codebase conventions; integration points clear |
| Pitfalls | MEDIUM | Patterns from training data; web search unavailable for verification |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Provider selection:** Ollama vs OpenAI vs Azure depends on user preference. Default to OpenAI for development, support all via LiteLLM.
- **Topic clustering accuracy:** Hybrid approach (embedding + LLM) needs validation against actual article content patterns. May need tuning of similarity threshold.
- **Template format:** "AI Five-Layer Cake" template based on existing ai-daily skill. Verify alignment with actual user needs during Phase 4.
- **Rate limit configurations:** Per-provider rate limits (Azure TPM vs OpenAI RPM) need user configuration. Defaults may need adjustment.

## Sources

### Primary (HIGH confidence)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm) - Unified LLM interface, verified version 1.83.4
- [PyPI: litellm](https://pypi.org/project/litellm/) - Version 1.83.4
- [PyPI: openai](https://pypi.org/project/openai/) - Version 2.30.0
- [PyPI: anthropic](https://pypi.org/project/anthropic/) - Version 0.89.0
- [ChromaDB Documentation](https://docs.trychroma.com/) - Multi-collection usage
- [Jinja2 Security](https://jinja.palletsprojects.com/) - Sandboxed environments

### Secondary (MEDIUM confidence)
- [Ollama Python Client](https://github.com/ollama/ollama-python) - Local model support
- [Sentence-Transformers](https://www.sbert.net/) - Embedding-based clustering
- Established LLM integration patterns from training data
- RSS reader architecture patterns from training data

### Tertiary (LOW confidence)
- tiktoken truncation strategy (first 60% + last 20%) - theoretical, needs validation
- Topic clustering threshold (0.65-0.70) - needs tuning against actual data
- Cost estimates ($5-10/month) - depends on actual usage patterns

---
*Research completed: 2026-04-07*
*Ready for roadmap: yes*
