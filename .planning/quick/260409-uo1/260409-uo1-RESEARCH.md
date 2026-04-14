# Phase Quick: Batch Summarization Optimization - Research

**Researched:** 2026/04/09
**Domain:** LLM batch processing, prompt engineering, asyncio concurrency
**Confidence:** HIGH

## Summary

The report pipeline makes up to 730 LLM calls: 200 articles x 3 calls (summarize + score + keywords) = 600, plus 30 cluster and 100 title calls. The core bottleneck is that `summarize_article_content()` makes 3 sequential-independent LLM calls per article, and the semaphore limits concurrency to 1.

**Key finding:** `llm_complete()` takes a single string prompt and returns a string. Litellm does NOT natively support multi-prompt batching in a single API call. The solution is to create a NEW multi-article prompt that asks for summary + quality + keywords for multiple articles in one JSON response. This reduces article processing from 3 calls to 1 call per batch of ~4 articles (200/4 = 50 calls instead of 600).

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Batch summarize is the primary optimization (not changing to a different LLM provider or architecture)
- Keep `summarize_article_content()` output format unchanged (backward compatible)
- Keep `pending_writes_v2` batch DB write pattern
- Maintain result quality

### Claude's Discretion
- Design the batch prompt structure
- Determine optimal batch size (3-5 articles)
- Set semaphore concurrency value
- Implement partial failure handling

### Deferred Ideas (OUT OF SCOPE)
- Changing LLM provider or model
- Modifying cluster or title translation logic

---

## Current Architecture

### Call Flow

```
process_one(article):
  if needs_summarize:
    summarize_article_content() → 3 x llm_complete()
      ├── summarize_text()      → 1 LLM call
      ├── score_quality()       → 1 LLM call
      └── extract_keywords()    → 1 LLM call
```

**Total:** 200 articles x 3 = 600 calls for article processing alone.

### Key Components

| Function | Purpose | Current Behavior |
|----------|---------|-----------------|
| `llm_complete()` (core.py:380) | Single-prompt LLM call | Takes 1 prompt string, returns 1 string. No native batching. |
| `LLMClient.batch_complete()` (core.py:335) | Concurrent multi-prompt | Runs prompts CONCURRENTLY but each is a SEPARATE API call. Not true batching. |
| `summarize_text()` (core.py:396) | Article summary | Single article → single summary |
| `score_quality()` (core.py:423) | Quality score 0-1 | Single article → single score |
| `extract_keywords()` (core.py:460) | Keyword extraction | Single article → keyword list |
| `summarize_article_content()` (summarize.py) | Orchestrates all 3 | Runs above 3 via `asyncio.gather()` (still 3 calls) |
| `process_one()` (report.py:708) | Per-article wrapper | Calls `summarize_article_content()`, semaphore=1 |
| `_translate_titles_batch_async()` (report.py:491) | Title translation | Already uses gather+semaphore but still 1 call per title |

### Semaphore Issue
`process_one()` uses `semaphore = asyncio.Semaphore(1)` (report.py:748), meaning only 1 concurrent LLM call at a time. Even if we use `asyncio.gather()`, the semaphore serializes all calls.

The `LLMClient` has `max_concurrency=5` (from settings), but the `LLMClient.semaphore` is created lazily and the semaphore in `bounded_process()` is always 1.

---

## Batch Summarization Design

### Approach: Multi-Article JSON Prompt

Create a NEW function `batch_summarize_articles()` that sends ONE prompt containing N articles and receives ONE JSON response with N results.

**Why this works:** The LLM can understand a prompt asking for structured JSON output for multiple articles. This is prompt engineering, not API batching.

### Batch Prompt Structure

```python
BATCH_SUMMARIZE_PROMPT = """你是一个专业的新闻内容分析师。请为每篇文章生成摘要、质量评分和关键词。

文章列表：
{article_list}

要求：
- 为每篇文章返回摘要（3-5句话）、质量评分（0-100）和3-5个关键词
- 返回格式：JSON数组，每项包含 title、summary、quality_score、keywords
- 质量评分考虑：内容深度、写作质量、独创性、实用性

JSON格式：
[
  {{"title": "文章标题", "summary": "摘要...", "quality_score": 85, "keywords": ["关键词1", "关键词2"]}},
  ...
]

仅返回JSON，不要包含其他内容。"""
```

### Article List Format

```
[1] 标题: xxx
    内容: (前500词)

[2] 标题: yyy
    内容: (前500词)
```

Truncate each article to ~500 words to fit multiple articles in context window.

### Response Parsing

```python
import json, re

async def batch_summarize_articles(articles: list[dict]) -> list[dict]:
    """Batch summarize multiple articles in one LLM call.

    Returns list of dicts with keys: title, summary, quality_score, keywords.
    """
    # Build article list string
    article_list = build_article_list(articles)  # truncate each to 500 words

    prompt = BATCH_SUMMARIZE_PROMPT.format(article_list=article_list)
    result = await llm_complete(prompt, max_tokens=2000, temperature=0.3)

    # Parse JSON array
    # Handle cases where model returns markdown code block
    json_str = re.sub(r"```json\n?|```\n?", "", result.strip())
    data = json.loads(json_str)

    # Validate and normalize
    results = []
    for item in data:
        results.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "quality_score": min(max(float(item.get("quality_score", 50)) / 100, 0.0), 1.0),
            "keywords": list(item.get("keywords", []))[:5],
        })
    return results
```

### Batch Size Decision

| Batch Size | LLM Calls (200 articles) | Pros | Cons |
|------------|--------------------------|------|------|
| 2 | 100 | Lower failure blast radius | More calls |
| 3 | 67 | Good balance | — |
| 4 | 50 | Fewer calls | Risk of context overflow, larger failure blast |
| 5 | 40 | Fewest calls | Too many articles per call may hurt quality |

**Recommendation:** Start with **batch size 3-4**, adjust based on quality and context window usage.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-article summarization | 3 separate calls per article | Multi-article JSON prompt | Reduces 600 calls to ~50-100 |
| Concurrent LLM calls | Sequential with Semaphore(1) | Semaphore(5-10) | Currently serializes everything |
| JSON parsing | string matching | `json.loads()` + `re.sub()` for markdown | Robust to model output variations |

**Key insight:** True LLM API batching (multiple prompts in one request) is NOT supported by litellm/OpenAI API. The "batch" here means prompt engineering: one prompt containing multiple articles, asking for JSON array response.

---

## Concurrency Increase

### Current Bottleneck

```python
# report.py:748
semaphore = asyncio.Semaphore(1)  # Only 1 concurrent LLM call!
```

### Recommended Change

```python
# report.py:748
semaphore = asyncio.Semaphore(5)  # Allow 5 concurrent LLM calls
```

Combined with batch summarization (50 calls for 200 articles instead of 600), concurrency of 5 means:
- 50 calls / 5 concurrent = 10 sequential "rounds" instead of 600 sequential calls
- Estimated time: ~10 * 2-3 seconds = 30-40 seconds instead of ~15-20 minutes

---

## Partial Failure Handling

### Failure Modes

1. **Entire batch fails** (network error, timeout) → retry the batch
2. **Some articles in batch succeed, some fail** → need per-article fallback
3. **JSON parse fails** → retry with same articles
4. **Individual article fields missing** → use defaults

### Strategy

```python
async def batch_summarize_with_fallback(articles: list[dict], batch_size: int = 3) -> list[dict]:
    """Batch summarize with per-article fallback on partial failure."""

    results: dict[int, dict] = {}  # index -> result
    failed_indices: set[int] = set()

    # Try batched first
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        indices = list(range(i, min(i + batch_size, len(articles))))

        try:
            batch_results = await batch_summarize_articles(batch)
            for idx, result in zip(indices, batch_results):
                if result.get("summary"):  # Valid result
                    results[idx] = result
                else:
                    failed_indices.add(idx)
        except Exception as e:
            logger.warning("Batch %d failed: %s. Falling back to individual.", i, e)
            failed_indices.update(indices)

    # Per-article fallback for failed
    for idx in failed_indices:
        article = articles[idx]
        try:
            # Call original summarize_article_content for single article
            summary, _, quality, keywords = await summarize_article_content(
                article, article.get("target_lang", "zh")
            )
            results[idx] = {
                "title": article.get("title", ""),
                "summary": summary,
                "quality_score": quality,
                "keywords": keywords,
            }
        except Exception as e:
            logger.error("Fallback also failed for %s: %s", article.get("id"), e)
            results[idx] = {
                "title": article.get("title", ""),
                "summary": "",
                "quality_score": 0.5,
                "keywords": [],
            }

    # Return in original order
    return [results[i] for i in range(len(articles))]
```

---

## Code Examples

### New Batch Summarization Function (core.py)

```python
BATCH_SUMMARIZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的新闻内容分析师。请为每篇文章生成摘要、质量评分和关键词。"),
    ("human", """文章列表：
{article_list}

要求：
- 为每篇文章返回摘要（3-5句话）、质量评分（0-100）和3-5个关键词
- 返回格式：JSON数组，每项包含 title、summary、quality_score、keywords
- 质量评分考虑：内容深度、写作质量、独创性、实用性
- 仅返回JSON数组，不要包含其他内容。""")
])

async def batch_summarize_articles(
    articles: list[dict],
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> list[dict]:
    """Summarize multiple articles in a single LLM call.

    Args:
        articles: List of dicts with 'title' and 'content' keys.
        max_tokens: Max response tokens.
        temperature: Sampling temperature.

    Returns:
        List of dicts with title, summary, quality_score (0-1), keywords.
    """
    if not articles:
        return []

    # Build article list with truncated content
    article_parts = []
    for i, art in enumerate(articles, 1):
        title = art.get("title", f"Article {i}")
        content = art.get("content") or art.get("description") or ""
        # Truncate to 500 words
        words = content.split()
        truncated = " ".join(words[:500])
        article_parts.append(f"[{i}] 标题: {title}\n内容: {truncated}")

    article_list = "\n\n".join(article_parts)

    # Build prompt
    prompt = BATCH_SUMMARIZE_PROMPT.format(article_list=article_list)

    result = await llm_complete(prompt, max_tokens=max_tokens, temperature=temperature)

    # Parse JSON
    import json, re
    json_str = re.sub(r"```json\n?|```\n?", "", result.strip())
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed: %s. Result was: %s", e, result[:200])
        raise

    # Normalize and validate
    results = []
    for item in data:
        score = float(item.get("quality_score", 50)) / 100
        score = min(max(score, 0.0), 1.0)
        results.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "quality_score": score,
            "keywords": list(item.get("keywords", []))[:5],
        })

    return results
```

### Integration with process_one (report.py)

```python
# New batch entry point in _cluster_articles_async
async def _process_articles_batch(articles: list[dict]) -> list[dict]:
    """Process articles in batches of 3-4 for summarization."""
    batch_size = 3
    all_results = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        try:
            results = await batch_summarize_articles(batch)
            all_results.extend(results)
        except Exception as e:
            logger.warning("Batch %d failed, falling back: %s", i, e)
            # Fall back to individual processing
            for art in batch:
                summary, _, quality, keywords = await summarize_article_content(art)
                all_results.append({
                    "title": art.get("title", ""),
                    "summary": summary,
                    "quality_score": quality,
                    "keywords": keywords,
                })

    return all_results
```

---

## Implementation Plan

### Phase 1: Add batch function (core.py)
1. Add `BATCH_SUMMARIZE_PROMPT` prompt template
2. Add `batch_summarize_articles()` function
3. Test with 2-3 articles, verify JSON parsing

### Phase 2: Integrate (report.py)
1. Modify `_cluster_articles_async()` to use batch summarization
2. Increase semaphore from 1 to 5
3. Add fallback to individual processing on batch failure

### Phase 3: Preserve backward compatibility (summarize.py)
1. Keep `summarize_article_content()` for single-article use cases
2. Add a flag to switch between batch and individual mode

### Phase 4: Tune
1. Adjust batch size based on quality and speed
2. Consider increasing semaphore to 8-10 if provider supports it

---

## Estimated Impact

| Optimization | Before | After |
|--------------|--------|-------|
| Article summarization | 600 calls (200 x 3) | ~67 calls (200 / 3) |
| Title translation | 100 calls (serial) | 100 calls (5 concurrent) |
| Total | ~730 | ~197 |

**Close to target of ~150.** Further reduction possible with:
- Larger batch size (4) → 50 calls for articles
- Batching title translations → ~10-20 batch calls for 100 titles
- Total: ~90-120 calls

---

## Open Questions

1. **Optimal batch size**: Start at 3, measure quality vs speed, adjust
2. **Translation batching**: Should we also batch title translations? `_translate_titles_batch_async` currently does 1 call per title with concurrency=1
3. **Context window**: With batch_size=3 and 500 words per article = ~1500 words + prompt overhead. Well within 32k context of MiniMax-M2.7

---

## Sources

### Primary (HIGH confidence)
- `src/llm/core.py` — `llm_complete()`, `summarize_text()`, `score_quality()`, `extract_keywords()` implementation
- `src/application/summarize.py` — `summarize_article_content()` orchestrator
- `src/application/report.py` — `process_one()`, `_translate_titles_batch_async()`, `_cluster_articles_async()`
- `src/llm/chains.py` — existing chain patterns (combined topic_title+layer chain as precedent)

### Secondary (MEDIUM confidence)
- Litellm batch documentation — `acompletion()` takes single prompt, not list
- LangChain `JsonOutputParser` usage for structured output (chains.py:242)

### Tertiary (LOW confidence)
- Optimal batch size of 3-4 — [ASSUMED] based on context window estimates

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified from source code
- Architecture: HIGH — verified from source code
- Pitfalls: HIGH — based on existing code patterns

**Research date:** 2026/04/09
**Valid until:** ~30 days (batch summarization pattern is stable)
