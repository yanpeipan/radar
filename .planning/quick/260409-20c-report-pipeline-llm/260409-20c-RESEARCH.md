# Quick Task: Report Pipeline LLM Optimization

**Researched:** 2026-04-09
**Task:** Optimize report pipeline: per-cluster classification instead of per-article, reducing LLM calls
**Confidence:** HIGH

## Summary

This task reduces LLM calls in the report pipeline by moving from per-article layer classification to per-cluster classification. The current pipeline classifies every article individually via `classify_article_layer()` even though articles are then grouped into clusters. The new pipeline will classify at the cluster level, after deduplication and K-Means clustering.

**Primary change:** Remove `classify_article_layer()` from `process_one()` in `_cluster_articles_v2_async`, add `classify_cluster_layer()` that operates on clustered articles.

## Current Flow (problematic)

```
ClusterArticles_v2_async:
  1. process_one() for EACH article → await classify_article_layer() [LLM call per article]
  2. deduplicate_articles() on all_processed + per-layer
  3. _cluster_articles_into_topics() per layer
  4. signals/creation classification (rule-based, no LLM)
```

Each article triggers an LLM call regardless of whether it will be merged into a cluster or deduped away.

## New Flow (optimized)

```
ClusterArticles_v2_async:
  1. deduplicate_articles() FIRST (before any LLM work)
  2. _cluster_articles_into_topics() per layer → returns topics with article lists
  3. classify_cluster_layer() per topic/cluster [1 LLM call per cluster]
  4. signals/creation classification (rule-based)
```

**LLM call reduction:** From N calls (one per article) to ~K calls (one per cluster, where K << N).

## Specific Changes

### 1. K-Means k formula (line 185 in `_cluster_articles_into_topics`)

**Current:**
```python
k = max(5, min(int(math.sqrt(n / 2)), 50))
```

**New:**
```python
k = max(10, n // 5)
```

This increases cluster count for larger datasets (e.g., n=100: old k=7, new k=20; n=200: old k=10, new k=40).

### 2. Small cluster merge threshold (lines 205, 318 in `_cluster_articles_into_topics`)

**Current:** `if len(group) <= 2` / `if t1["sources_count"] <= 2`
**New:** `if len(group) <= 3` / `if t1["sources_count"] <= 3`

This keeps small clusters intact rather than merging them, preserving more granular topic groupings for cluster-level classification.

### 3. New function: `classify_cluster_layer()`

**Location:** `src/application/report.py` near `classify_article_layer()` (around line 485)

**Signature:**
```python
async def classify_cluster_layer(articles: list[dict], target_lang: str = "zh") -> str:
    """Classify a cluster of articles into one of the five-layer cake categories.

    Args:
        articles: List of article dicts with 'title' and 'summary' keys.
        target_lang: Target language code (zh, en, ja, ko).

    Returns:
        One of: AI应用, AI模型, AI基础设施, 芯片, 能源
    """
```

**Implementation approach:** Build a combined prompt with all article titles and summaries (truncated), use same `get_classify_chain()` with adapted input format. The chain prompt at `CLASSIFY_PROMPT` expects `{title}` and `{content}` — a new cluster variant should be created that takes `{article_list}` instead.

### 4. Chain adaptation for cluster classification

**Current chain input:** Single title + 300-word content sample
**Cluster chain input:** List of article titles + summaries

A new `CLASSIFY_CLUSTER_PROMPT` variant should be added to `src/llm/chains.py`:

```python
CLASSIFY_CLUSTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Classify this cluster of articles into ONE of the following categories:
- AI应用 (Application): AI products, tools, and services used by end users
- AI模型 (Model): AI model releases, benchmarks, research papers, training methods
- AI基础设施 (Infrastructure): Cloud platforms, MLOps tools, deployment, APIs
- 芯片 (Chip): AI hardware, GPUs, custom silicon, semiconductor news
- 能源 (Energy): AI energy consumption, data center power, carbon footprint, renewable energy for AI

Consider all articles together and return the dominant category for the cluster.""",
        ),
        (
            "human",
            "Article Titles and Summaries:\n{article_list}\n\nReturn ONLY the category name.",
        ),
    ]
)

def get_classify_cluster_chain():
    """Returns LCEL chain for cluster classification."""
    return CLASSIFY_CLUSTER_PROMPT | _get_llm_wrapper() | StrOutputParser()
```

### 5. Remove per-article LLM call from `process_one()`

In `_cluster_articles_v2_async`, the `process_one()` function (line 715) currently:
```python
text = summary or full.get("content") or full.get("description") or ""
layer = await classify_article_layer(text, title)  # ← REMOVE THIS
```

After removal, `process_one` only does on-demand summarization and returns the article dict. The `layer` field will be populated at the cluster level instead.

### 6. Assign cluster layers after topic generation

In `_cluster_articles_v2_async`, after `_cluster_articles_into_topics()` returns (line 789), iterate over topics and call `classify_cluster_layer()`:

```python
for layer_name in LAYER_KEYS:
    arts = articles_by_layer.get(layer_name, [])
    topics = await _cluster_articles_into_topics(arts, target_lang)
    # Classify each topic into a layer sub-category
    for topic in topics:
        article_list = "\n".join(
            f"- {a.get('title', 'Untitled')}: {a.get('summary', '')[:100]}"
            for a in topic["sources"][:10]
        )
        topic["layer"] = await classify_cluster_layer(topic["sources"], target_lang)
    layers_data.append(...)
```

Wait — topics are already within a layer. The `classify_cluster_layer()` here would classify the cluster's *sub-theme* within the layer, not the layer itself. Re-reading the task: "Adding classify_cluster_layer() function that takes all article titles+summaries in a cluster and classifies once."

This means each topic/cluster gets ONE classification call, replacing N per-article calls within that cluster. Since topics are already grouped by layer in `layers_data`, the cluster classification here might be for sub-layer refinement or tagging. But the five-layer taxonomy is the primary classification...

Actually, looking more carefully at the current flow: `process_one` calls `classify_article_layer()` which classifies into the 5-layer taxonomy. Topics are grouped within each layer. So there may be no need to re-classify at the topic level if the layer is already correct.

**Alternative interpretation:** The task wants to move the 5-layer classification from per-article to per-cluster, so that instead of `process_one → classify_article_layer()`, the cluster gets classified once. In that case, `articles_by_layer` wouldn't need pre-population by layer — instead, all articles would be clustered first (without layer classification), then each cluster gets classified into a layer.

Let me clarify the new flow based on this interpretation:

```
1. deduplicate_articles() on all articles
2. _cluster_articles_into_topics() on ALL articles (not per-layer) → topics
3. classify_cluster_layer() per topic → assigns layer to each topic
4. Group topics by layer for template rendering
```

This would further reduce calls: currently N articles are classified, then grouped; with this approach only K clusters are classified.

**Recommendation:** The second interpretation is cleaner and matches "per-cluster classify (not per-article)" more directly. But it requires changing the structure since `_cluster_articles_into_topics` currently returns topics within a layer context. The change should pass all deduplicated articles (without layer filter) to `_cluster_articles_into_topics`, then classify each resulting topic.

## Common Pitfalls

### Pitfall 1: Cluster too large for prompt context
**Problem:** A cluster with 50+ articles could produce a very long `article_list` string.
**Avoid:** Limit to first 15-20 articles per cluster when building the article list for classification.

### Pitfall 2: Empty cluster on summarization failure
**Problem:** If all articles in a cluster fail to summarize, the cluster has no useful text.
**Avoid:** Always include article titles alongside summaries in the prompt; titles alone often suffice for classification.

### Pitfall 3: Semaphore concurrency blowup
**Problem:** If many clusters are generated, parallel `classify_cluster_layer()` calls could overwhelm the LLM.
**Avoid:** Keep the existing `asyncio.Semaphore(5)` pattern for bounded concurrency.

## Integration Points

| What | Where | How |
|------|-------|-----|
| Add `CLASSIFY_CLUSTER_PROMPT` | `src/llm/chains.py` | New prompt template near `CLASSIFY_PROMPT` |
| Add `get_classify_cluster_chain()` | `src/llm/chains.py` | Factory function near `get_classify_chain()` |
| Add `classify_cluster_layer()` | `src/application/report.py` | Near `classify_article_layer()` |
| Change k formula | `_cluster_articles_into_topics` line 185 | Simple replacement |
| Change merge threshold | `_cluster_articles_into_topics` lines 205, 318 | `<=2` to `<=3` |
| Remove per-article classify | `_cluster_articles_v2_async` `process_one()` | Remove `classify_article_layer()` call |
| Reorder pipeline | `_cluster_articles_v2_async` | Move deduplicate before clustering |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `classify_cluster_layer()` uses a new chain variant, not the existing `get_classify_chain()` | Specific Changes #3 | The existing chain takes single title+content; cluster variant needs multi-article input. If a single-chain approach is preferred, the prompt would need to handle both cases. |
| A2 | Cluster-level classification replaces layer-level classification entirely | New Flow | If some downstream code depends on per-article layer assignment, it would break. The `process_one` return dict includes `layer` field — callers may use this. |

## Open Questions

1. **Does downstream code depend on `article['layer']` from `process_one`?**
   - Currently `process_one` returns `processed` with `layer` field populated
   - If any caller reads `article_dict["layer"]`, removing it would break
   - The template renders `layers` → `topics` → `sources`, not individual article layers
   - **Recommendation:** Verify no code reads per-article `layer` field after `process_one`

2. **Should cluster classification happen before or after `_cluster_articles_into_topics`?**
   - Currently topics are generated within each layer via `_cluster_articles_into_topics(arts, target_lang)` where `arts = articles_by_layer.get(layer_name, [])`
   - If we pass all articles at once (not pre-filtered by layer), clustering is layer-agnostic
   - Then `classify_cluster_layer()` assigns the layer to each cluster
   - **Recommendation:** This approach is cleaner — fewer code paths

## Sources

- `src/application/report.py` — current `_cluster_articles_v2_async`, `_cluster_articles_into_topics`, `classify_article_layer()`
- `src/llm/chains.py` — `CLASSIFY_PROMPT`, `get_classify_chain()`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — uses existing LLM chain infrastructure
- Architecture: HIGH — clear before/after flow, minimal scope
- Pitfalls: MEDIUM — edge cases around cluster size untested

**Research date:** 2026-04-09
**Valid until:** 30 days (LLM chain interface stable)
