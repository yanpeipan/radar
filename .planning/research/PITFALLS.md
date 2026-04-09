# Pitfalls Research: LLM Integration for Feedship v1.11

**Domain:** LLM-powered features (summarization, quality scoring, keyword extraction, topic clustering, daily reports)
**Project:** Feedship v1.11 - Python RSS Reader CLI with LLM enhancements
**Researched:** 2026-04-07
**Confidence:** MEDIUM (established patterns from training data; web search unavailable for direct verification)

---

## Executive Summary

Adding LLM features to a feed reader presents distinct challenges from typical LLM applications. The scale problem is fundamental: 110 RSS feeds with 50+ articles each means thousands of potential LLM calls per fetch cycle. Cost control, rate limiting, and graceful degradation are not optional - they are requirements from day one.

This research identifies 9 critical pitfalls across 5 categories: Cost Management, Reliability, Quality, Performance, and Security. Each pitfall includes prevention strategies mapped to implementation phases.

**Key insight:** Most pitfalls are solvable with standard patterns (caching, retries, fallbacks) but require deliberate architectural decisions early. Waiting until Phase 2 or 3 to address them increases cost 10x-100x.

---

## Critical Pitfalls

### 1. API Cost Blowup — "Thousand LLM Calls Per Fetch"

**What goes wrong:**
110 feeds × ~50 articles × 5 LLM features (summary, score, keywords, cluster, report) = 27,500 LLM calls per full fetch cycle. At $0.15/1K tokens for GPT-4o-mini, even minimal content generates hundreds of dollars daily.

**Why it happens:**
No cost gating. Naive implementation calls LLM for every article, every feature, every fetch cycle. User discovers $500 bill at end of month.

**Consequences:**
- Unexpected large bills
- Feature disabled due to cost
- User distrust of automated features

**Prevention: Phase 1 — Cost Architecture**
```
Implementation requirements:
1. Feed weighting: Only summarize/score articles from high-weight feeds
2. Recency gating: Only process articles from last 24-48 hours
3. Deduplication: Never call LLM for same article twice (check summarized_at)
4. Batch calls: Group multiple articles into single LLM call where possible
5. Budget limits: Hard cap on daily LLM calls per user
```

**Detection warning signs:**
- LLM call count increasing linearly with article count (should be sublinear)
- No caching metrics in logs
- Missing `summarized_at` / `scored_at` checks before LLM calls

**Phase to address:** Phase 1 — Core LLM Infrastructure

---

### 2. Rate Limiting — "OpenAI Rejected My Request"

**What goes wrong:**
Overnight batch job hits OpenAI API limits. 429 errors cascade. Job fails silently or retries into oblivion.

**Why it happens:**
No retry logic with backoff. Direct API calls without LiteLLM abstraction. Azure and OpenAI have different rate limit characteristics.

**Prevention: Phase 1 — LLM Client Abstraction**
```
Implementation requirements:
1. Use LiteLLM as unified client (supports OpenAI, Azure, Ollama, Anthropic)
2. Configure exponential backoff: max_retries=3, base_delay=1s, max_delay=60s
3. Implement circuit breaker: after 5 consecutive failures, fail fast for 5 minutes
4. Queue requests: asyncio queue with controlled concurrency (max 5 concurrent)
5. Per-provider rate limit awareness: Azure has different TPM limits than OpenAI
```

**LiteLLM example:**
```python
from litellm import acompletion
import litellm

# Configure retries with exponential backoff
litellm.max_retries = 3
litellm.retry_after_header = True  # Respect Retry-After header

async def safe_completion(model: str, messages: list):
    try:
        return await acompletion(model=model, messages=messages)
    except Exception as e:
        # LiteLLM handles retries and backoff automatically
        raise
```

**Detection warning signs:**
- 429 errors in logs
- Linear retry loop consuming API quota
- No differentiation between rate limit and auth errors

**Phase to address:** Phase 1 — LLM Client Abstraction

---

### 3. LLM Hallucination — "Confident Wrong Quality Scores"

**What goes wrong:**
Quality score of 0.95 given to article that is actually low-quality. Summary contains facts not present in article. User acts on false information.

**Why it happens:**
LLMs generate plausible-sounding but incorrect outputs. Without verification, user cannot distinguish accurate from hallucinated.

**Prevention: Phase 2 — Quality Assurance**
```
Implementation requirements:
1. Chain-of-thought prompting: Require reasoning before final score
2. Confidence scores: Ask model to output confidence 0.0-1.0 alongside score
3. Self-verification prompt: "Verify this summary matches the article content"
4. Threshold gating: Low-confidence outputs flagged, not hidden
5. Human review sample: 5% of outputs reviewed for accuracy
```

**Example with confidence:**
```python
QUALITY_PROMPT = """Rate article quality 0.0-1.0. Output JSON with score, confidence, and reasoning.

Article Title: {title}
Content (first 1000 chars): {content[:1000]}

Output JSON:
{
  "score": 0.0-1.0,
  "confidence": 0.0-1.0,
  "reasoning": "explanation of factors",
  "factual_claims": ["list of specific claims for verification"]
}"""

# Reject low-confidence outputs
if result["confidence"] < 0.6:
    logger.warning(f"Low confidence score ({result['confidence']}) for {article_id}")
    # Flag for manual review or use fallback
```

**Detection warning signs:**
- All quality scores cluster at extremes (0.9+ or 0.3-)
- No variance across batch (all articles scored identically)
- Summary mentions specific numbers/dates not in original

**Phase to address:** Phase 2 — LLM Output Quality

---

### 4. Offline Ollama Failure — "Ollama Not Running, Everything Broken"

**What goes wrong:**
User configured local Ollama. Ollama crashes or not started. Entire LLM feature set fails. No graceful fallback to cloud.

**Why it happens:**
No fallback chain. Code assumes Ollama is available. No detection of unavailable provider.

**Prevention: Phase 1 — Provider Fallback Chain**
```
Implementation requirements:
1. Define fallback chain: Ollama -> OpenAI -> Azure -> Anthropic
2. Health check on startup: Verify at least one provider is available
3. Automatic fallback: On Ollama failure, try next provider
4. User notification: Inform user which provider is active
5. Force flag: --force-provider openai to override automatic selection
```

**Implementation pattern:**
```python
PROVIDER_CHAIN = ["ollama/llama3", "openai/gpt-4o-mini", "azure/gpt-4o-mini"]

async def get_completion_with_fallback(messages: list):
    last_error = None

    for provider in PROVIDER_CHAIN:
        try:
            # Try each provider in chain
            response = await acompletion(model=provider, messages=messages)
            return response
        except Exception as e:
            last_error = e
            logger.warning(f"Provider {provider} failed: {e}")
            continue

    # All providers failed
    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")
```

**Detection warning signs:**
- "Connection refused" or "Ollama not running" errors
- Feature fails entirely when offline
- No logging of which provider was attempted

**Phase to address:** Phase 1 — Multi-Provider Support

---

### 5. Content Truncation — "Long Article Summaries Missing Key Points"

**What goes wrong:**
Article of 10,000 words truncated to 4,000 tokens. Summary only covers first part. Key conclusion at end is missed.

**Why it happens:**
LLM context windows are finite. Without chunking strategy, long articles lose tail content.

**Prevention: Phase 1 — Content Processing**
```
Implementation requirements:
1. Token estimation: Use tiktoken to count tokens before sending
2. Truncation strategy: Keep first 8K tokens (most articles put key info early)
3. Chunking option: For critical long-form content, process in overlapping chunks
4. Content warning: Flag if article exceeds 10K tokens, note potential truncation
5. Section-aware: Prefer first paragraph, last paragraph, first sentence of each section
```

**Implementation pattern:**
```python
import tiktoken

def truncate_to_token_limit(content: str, max_tokens: int = 8000) -> str:
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(content)

    if len(tokens) <= max_tokens:
        return content

    # Keep first 60% + last 20% (key info often at beginning and end)
    begin = tokens[:int(max_tokens * 0.6)]
    end = tokens[-int(max_tokens * 0.2):]
    truncated = encoding.decode(begin + end)

    logger.warning(f"Content truncated from {len(tokens)} to {max_tokens} tokens")
    return truncated
```

**Detection warning signs:**
- Long articles consistently receive poor summaries
- Users report "summary misses the point"
- No token counting in logs

**Phase to address:** Phase 1 — Content Processing

---

### 6. Slow Inference — "Local Ollama Takes 30 Seconds Per Article"

**What goes wrong:**
Ollama on CPU generates 1-5 tokens/second. 100 articles × 5 features = 500 LLM calls. At 3 tok/s and 200 tokens per call = 33,000 seconds = 9 hours.

**Why it happens:**
No async handling, no progress indication, no timeout, no streaming. Blocking on slow local inference.

**Prevention: Phase 2 — Async Pipeline**
```
Implementation requirements:
1. Async throughout: Use asyncio for all LLM calls
2. Timeout handling: Max 30s per single-article call, fail gracefully
3. Progress bars: rich.Progress for batch operations
4. Streaming output: Stream tokens to user for immediate feedback
5. Concurrent batching: Send up to 10 articles in single batch (LiteLLM batch API)
```

**Implementation pattern:**
```python
import asyncio
from rich.progress import Progress, SpinnerColumn, TextColumn

async def process_articles_async(articles: list[dict]) -> list[dict]:
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent

    async def process_one(article: dict) -> dict:
        async with semaphore:
            try:
                # 30 second timeout
                return await asyncio.wait_for(
                    llm_process_article(article),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Timeout processing {article['id']}")
                return {"error": "timeout", "article_id": article["id"]}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(f"Processing {len(articles)} articles...", total=len(articles))
        results = await asyncio.gather(*[process_one(a) for a in articles])
        progress.update(task, completed=len(articles))

    return results
```

**Detection warning signs:**
- Batch processing time increases linearly with article count
- No progress indication during long operations
- Single fetch takes more than 5 minutes

**Phase to address:** Phase 2 — Async Processing Pipeline

---

### 7. Duplicate Summarization — "Same Article Summarized 50 Times"

**What goes wrong:**
Article fetched on Monday, summarized. Fetched again Tuesday (new entry in feed). Summarized again. User sees duplicate summaries. Cost multiplies.

**Why it happens:**
No deduplication check. Article identified by URL but URL may include tracking parameters. `summarized_at` field exists but not checked before LLM call.

**Prevention: Phase 1 — Deduplication & Caching**
```
Implementation requirements:
1. Normalized URL: Strip tracking params (?utm_source, ?fbclid, etc.)
2. summarized_at check: Skip if not None and not --force
3. Stable article ID: Use content hash (SHA256 of title+content) as dedup key
4. Time-based dedup: Same title within 24h = same article
5. Batch dedup: Pre-fetch all article IDs, filter before LLM calls
```

**SQLite schema:**
```sql
CREATE TABLE article_summaries (
    article_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,        -- SHA256 of title+content
    summary TEXT,
    summarized_at TEXT,
    model TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE INDEX idx_summarized ON articles(summarized_at) -- fast dedup check
```

**Implementation:**
```python
async def summarize_if_needed(article: dict, force: bool = False) -> str | None:
    # Check cache
    if not force and article.get("summarized_at"):
        logger.debug(f"Skipping {article['id']} - already summarized")
        return None

    # Check content hash for near-duplicates
    content_hash = hash_article_content(article)
    existing = find_by_content_hash(content_hash)
    if existing and not force:
        logger.debug(f"Skipping {article['id']} - duplicate content")
        return None

    # Generate summary
    return await llm_summarize(article)
```

**Detection warning signs:**
- LLM call count exceeds unique articles × features
- Summaries for articles with same title but different URLs
- No `summarized_at` index in database

**Phase to address:** Phase 1 — Deduplication & Caching

---

### 8. Template Injection — "Malicious Content in Daily Report"

**What goes wrong:**
RSS article contains `{{ malicious_variable }}`. Jinja2 template engine evaluates it. Confidential data leaked or system compromised.

**Why it happens:**
User-provided content rendered through Jinja2 template without escaping. Template injection is equivalent to code injection.

**Prevention: Phase 3 — Report Generation**
```
Implementation requirements:
1. Sandboxed rendering: Use Jinja2 in sandboxed environment
2. No eval(): Never use eval() on user content
3. Autoescape: Enable autoescape for all template variables
4. Whitelist filters: Only allow specific Jinja2 filters (default_filters only)
5. User templates restricted: Warn if custom template path provided
```

**Safe template rendering:**
```python
from jinja2 import Environment, BaseLoader, select_autoescape

# Sandboxed environment - no access to Python builtins
env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(['html', 'xml']),
    enable_async=True
)

# Only expose safe operations
SAFE_GLOBALS = {
    'tojson': tojson,  # Safe JSON encoding
    'str': str,
    'len': len,
    'round': round,
}

template = env.from_string(user_template)
output = template.render(
    **safe_globals,
    articles=articles,
    # Never pass raw article content directly
)
```

**Detection warning signs:**
- User reports seeing unexpected data in reports
- Template errors that look like Python exceptions
- Custom templates that work but with strange side effects

**Phase to address:** Phase 3 — Report Generation (last, after other features validated)

---

### 9. ChromaDB Collection Conflicts — "Summary Embeddings Polluting Article Search"

**What goes wrong:**
Summary embeddings stored in same ChromaDB collection as article content embeddings. Semantic search for "AI chips" returns summaries instead of full articles. Collection name collisions across features.

**Why it happens:**
No collection naming convention. Different features share "articles" collection. ChromaDB has no schema enforcement.

**Prevention: Phase 1 — ChromaDB Namespacing**
```
Implementation requirements:
1. Collection naming: {feature}_{version} (e.g., article_content_v1, article_summary_v1)
2. Separate collections: One collection per embedding type
3. Version suffix: Allow future migrations without breaking existing data
4. Collection registry: Central list of all collections with purposes
```

**Collection registry:**
```python
COLLECTIONS = {
    "article_content_v1": {
        "purpose": "Full article semantic search",
        "embedding_model": "all-MiniLM-L6-v2",
        "dimension": 384,
    },
    "article_summary_v1": {
        "purpose": "Summary semantic search",
        "embedding_model": "all-MiniLM-L6-v2",
        "dimension": 384,
    },
    "article_keywords_v1": {
        "purpose": "Keyword semantic search",
        "embedding_model": "all-MiniLM-L6-v2",
        "dimension": 384,
    },
}

def get_collection(name: str):
    return chroma_client.get_or_create_collection(
        name=name,
        metadata={"purpose": COLLECTIONS[name]["purpose"]}
    )
```

**Detection warning signs:**
- Search results show unexpected types (summaries when expecting articles)
- Collection metadata is empty or missing
- ChromaDB errors about duplicate IDs

**Phase to address:** Phase 1 — ChromaDB Infrastructure

---

## Phase-Specific Pitfall Mapping

| Phase | Features | Critical Pitfalls | Priority |
|-------|----------|-------------------|----------|
| **Phase 1: Core LLM Infrastructure** | LLM client, basic summarization, scoring, keyword extraction | #1 Cost Blowup, #2 Rate Limiting, #4 Offline Ollama, #5 Content Truncation, #7 Duplicate Summarization, #9 ChromaDB Conflicts | P0 |
| **Phase 2: Async Pipeline** | Batch processing, streaming, progress bars | #6 Slow Inference | P0 |
| **Phase 3: Quality & Reports** | Daily reports, topic clustering, confidence scoring | #3 Hallucination, #8 Template Injection | P1 |

---

## Pitfall Severity Matrix

| Pitfall | Severity | Cost Impact | User Impact | Fix Complexity |
|---------|----------|-------------|-------------|----------------|
| API Cost Blowup | CRITICAL | $$$$ | Feature disabled | Medium |
| Rate Limiting | CRITICAL | $$ | Failures, no output | Low |
| Offline Ollama | HIGH | $ | Feature unavailable | Low |
| Content Truncation | HIGH | $$ | Poor quality output | Low |
| Slow Inference | HIGH | $$ | Poor UX, timeouts | Medium |
| Duplicate Summarization | MEDIUM | $$$ | Wasted API calls | Low |
| Hallucination | HIGH | N/A | Wrong decisions | High |
| Template Injection | CRITICAL | N/A | Data leak, RCE | Medium |
| ChromaDB Conflicts | LOW | $ | Search quality | Low |

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip LiteLLM, use raw OpenAI SDK | Faster initial dev | Provider lock-in, no retries | Never |
| No caching layer | Simpler code | 10x-100x cost | Never for production |
| Single provider, no fallback | Simpler config | System fails if provider down | Only for dev |
| No token counting | Simpler processing | Hallucination risk, truncation | Never |
| Skip content hash dedup | Faster dev | Duplicate LLM calls | Only for prototype |
| User templates without sandbox | More flexible | Security vulnerability | Never |
| Single ChromaDB collection | Simpler setup | Data contamination | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LiteLLM + Azure | Not configuring Azure API base | Set `os.environ["AZURE_API_BASE"]` |
| LiteLLM + Ollama | Wrong model name format | Use `ollama/llama3` not `llama3` |
| ChromaDB + concurrent writes | Collection locking | Use asyncio.Lock per collection |
| Jinja2 + user content | Not auto-escaping | Always use autoescape or safe globals |
| tiktoken + long content | Memory blowup | Stream encoding for 100K+ token content |

---

## "Looks Done But Isn't" Checklist

- [ ] **Cost control:** LLM call count logged and monitored per fetch cycle
- [ ] **Rate limiting:** 429 errors handled with exponential backoff
- [ ] **Fallback:** Ollama failure triggers cloud fallback without user action
- [ ] **Content limits:** Token count logged for every LLM input
- [ ] **Inference speed:** Batch of 10 articles completes in under 60 seconds
- [ ] **Deduplication:** `summarized_at` checked before every LLM call
- [ ] **Template safety:** User-provided templates rendered in sandbox
- [ ] **Collection isolation:** Each feature uses separate ChromaDB collection

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cost blowup (month-end) | HIGH | Disable LLM features, audit logs, implement better caching |
| Rate limit cascade | MEDIUM | Wait for cooldown, implement backoff, reduce concurrency |
| Ollama offline | LOW | Restart Ollama, check `ollama list` for model availability |
| Truncated summary | MEDIUM | Re-process with higher token limit, notify user |
| Slow inference | MEDIUM | Reduce batch size, use streaming, add timeout |
| Duplicate summarization | LOW | Clean up with dedup query, refund via cache |
| Hallucination | HIGH | Audit prompt, add confidence threshold, flag for review |
| Template injection (detected) | HIGH | Kill current report, sanitize inputs, alert user |
| Collection conflict | LOW | Migrate to new collection with correct naming |

---

## Sources

**Primary (HIGH confidence):**
- LiteLLM documentation: Unified LLM client with built-in retries and fallbacks
- Jinja2 security documentation: Sandboxed environments and autoescape
- ChromaDB documentation: Collection management and namespacing

**Secondary (MEDIUM confidence):**
- Established LLM integration patterns from training data
- tiktoken documentation: Token counting and truncation
- RSS reader architecture patterns from training data

**Note:** Web search was unavailable during this research. All findings should be verified against current documentation before implementation.

---

*Pitfalls research for: Feedship v1.11 LLM Features*
*Researched: 2026-04-07*
*Confidence: MEDIUM (established patterns; web search unavailable for verification)*
