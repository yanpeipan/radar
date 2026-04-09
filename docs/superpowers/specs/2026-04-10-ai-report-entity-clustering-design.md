# AI Report Entity Clustering — Design Specification

**Date:** 2026-04-10
**Author:** feedship team
**Status:** Draft
**Version:** 1.0

---

## 1. Problem Statement

当前的 report pipeline 对新闻做**语义聚类**（thematic clustering），按主题分组文章。但当输入规模达到3333篇/天时，这种方式的局限性显现：

- "Google Gemma 4 开源" 和 "Google 发布 Gemma 4" 会被分到不同的语义簇
- 用户无法一眼看到某个实体（如 "Google Gemma 4"）的完整信息
- 日报长度不可控，最多可能30+页

**目标：** 重构 report pipeline，实现**实体聚类**（entity-based clustering），把关于同一实体（如产品、公司、模型）的文章聚合在一起，配以维度标签（发布/融资/研究/生态），生成更可消费的日报。

---

## 2. Design Principles

1. **CLI 完全兼容** — `feedship report --since X --until Y --language zh` 行为不变，结果更智能
2. **LLM 成本可控** — ~170次/报告 run（当前 ~192次，持平或更少）
3. **可独立验证** — 每个 layer 可以单独测试
4. **向后兼容** — 保留 Jinja2 模板系统，仅更新数据结构
5. **信号过滤前置** — 3333篇 → ~300篇高价值文章，再进入实体聚类

---

## 3. Architecture Overview

```
feedship report --since 2026-04-09 --until 2026-04-10 --language zh
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 0: Signal Filter (0 LLM)                             │
│  ────────────────────────────────────────────────────────    │
│  Input:  all raw articles from date range                   │
│  Output: ~300 high-signal articles                          │
│                                                              │
│  Rules (all applied in order):                              │
│  1. SHA256 exact dedup                                      │
│  2. quality_score >= 0.6                                    │
│  3. feed_weight >= 0.5                                      │
│  4. recency weight: published_at within range               │
│  5. event_signal boost: title matches funding/release/...   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: NER + Entity Resolution (LLM batch, ~30 calls)   │
│  ────────────────────────────────────────────────────────    │
│  Input:  ~300 filtered articles                             │
│  Output: articles with entity tags and normalized names      │
│                                                              │
│  Process:                                                    │
│  1. Batch NER: 10 articles per LLM call                    │
│  2. Extract entity types: ORG, PRODUCT, MODEL, PERSON      │
│  3. Normalize: "Google Gemma 4" / "Gemma-4" → google_gemma_4│
│  4. Fallback: if NER fails, use feed_id grouping           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: Entity Clustering (LLM, ~40 calls)                │
│  ────────────────────────────────────────────────────────    │
│  Input:  articles tagged with entities                      │
│  Output: 30-50 entity topics                                │
│                                                              │
│  Process:                                                    │
│  1. Group articles by normalized entity_id                  │
│  2. Within each entity: sub-cluster by dimension             │
│  3. Per entity: LLM call → headline + signals + layer      │
│  4. Large event split: if articles > threshold, split dims  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: TLDR Generation (1 LLM call)                      │
│  ────────────────────────────────────────────────────────    │
│  Input:  top 10 entity topics by quality_weight             │
│  Output: 1-sentence TLDR per entity                         │
│                                                              │
│  Formula: quality_weight = quality_score × article_count     │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: Render (Jinja2, 0 LLM)                          │
│  ────────────────────────────────────────────────────────    │
│  Output: Markdown日报                                        │
│                                                              │
│  Sections:                                                   │
│  1. Today's Top 10 AI News (TLDR)                          │
│  2. By Layer (五层蛋糕)                                     │
│  3. By Dimension (发布/融资/研究/生态)                       │
│  4. Deep Dive (大事件拆分)                                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Data Structures

### 4.1 Article (enriched)

```python
@dataclass
class ArticleEnriched:
    id: str
    title: str
    link: str
    summary: str
    quality_score: float          # 0.0-1.0
    feed_weight: float            # 0.0-1.0
    published_at: str
    feed_id: str

    # Added by Layer 1
    entities: list[EntityTag] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)  # e.g. ["release", "funding"]

@dataclass
class EntityTag:
    name: str          # Raw name: "Google Gemma 4"
    type: str          # ORG | PRODUCT | MODEL | PERSON
    normalized: str    # Canonical: "google_gemma_4"
```

### 4.2 Entity Topic

```python
@dataclass
class EntityTopic:
    entity_id: str               # "google_gemma_4"
    entity_name: str             # "Google Gemma 4"
    layer: str                   # "AI模型"

    headline: str                 # "Google Gemma 4 开源：性能超越Llama 3"

    # Articles grouped by dimension
    dimensions: dict[str, list[ArticleEnriched]] = field(default_factory=dict)
    # {
    #   "release": [art1, art2],
    #   "open_source": [art3, art4, art5],
    #   "research": [art6]
    # }

    articles_count: int           # Total: 87
    signals: list[str]           # ["开源", "SOTA", "多模态", "MIT许可证"]
    tldr: str                    # Generated in Layer 3

    # For ranking
    quality_weight: float         # quality_score × articles_count
```

### 4.3 Report Render Data

```python
@dataclass
class ReportData:
    tldr_top10: list[EntityTopic]              # Sorted by quality_weight desc
    by_layer: dict[str, list[EntityTopic]]    # {"AI模型": [...], ...}
    by_dimension: dict[str, list[EntityTopic]]# {"release": [...], ...}
    deep_dive: list[EntityTopic]               # articles_count > 50, split by dim
    date_range: dict[str, str]                  # {"since": "2026-04-09", "until": "2026-04-10"}
    target_lang: str                            # "zh"
```

### 4.4 Five Dimensions

| Dimension | Chinese | Keywords |
|-----------|---------|----------|
| `release` | 发布 | release, launch, announce, 发布, 推出 |
| `funding` | 融资 | funding, raise, series, vc, 融资, 投资 |
| `research` | 研究 | research, paper, study, benchmark, 研究, 论文 |
| `ecosystem` | 生态 | open source, acquisition, partnership, merger, 生态, 开源, 收购 |
| `policy` | 监管 | regulation, policy, government, ban, 监管, 政策 |

### 4.5 Five Layers (不变)

| Layer | Chinese |
|-------|---------|
| `AI应用` | AI应用 |
| `AI模型` | AI模型 |
| `AI基础设施` | AI基础设施 |
| `芯片` | 芯片 |
| `能源` | 能源 |

---

## 5. Component Design

### 5.1 Signal Filter — `src/application/report/filter.py`

**Responsibility:** Apply rules to filter 3333 → ~300 high-signal articles.

**Class:** `SignalFilter`

```python
class SignalFilter:
    def __init__(
        self,
        quality_threshold: float = 0.6,
        feed_weight_threshold: float = 0.5,
        event_signal_boost: bool = True,
    ):
        ...

    def filter(self, articles: list[Article]) -> list[Article]:
        """Apply all filter rules in order. Returns filtered list."""
        ...

    def _apply_all_rules(self, article: Article) -> bool:
        """Return True if article passes all rules."""
        ...
```

**Filter Rules (applied in order, article must pass ALL):**

1. **Exact dedup** — SHA256(title + content[:500]) seen before
2. **Quality gate** — `quality_score >= self.quality_threshold`
3. **Feed weight gate** — `feed_weight >= self.feed_weight_threshold`
4. **Recency** — `published_at` within date range
5. **Event signal boost** — title matches event keywords (release/funding/acquisition/...) gets +0.1 quality boost

**Config:** Thresholds are CLI-configurable in future; hardcoded for v1.

---

### 5.2 NER Extractor — `src/application/report/ner.py`

**Responsibility:** Extract named entities from articles using LLM batch processing.

**Class:** `NERExtractor`

```python
class NERExtractor:
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    async def extract_batch(
        self, articles: list[Article]
    ) -> list[ArticleEnriched]:
        """Process articles in batches, returns enriched articles."""
        ...

    async def _ner_one_batch(
        self, batch: list[Article]
    ) -> list[tuple[str, list[EntityTag]]]:
        """Single LLM call for NER. Returns [(article_id, entities)]."""
        ...
```

**LLM Chain:** New chain `get_ner_chain()` in `chains.py`:

```python
# Prompt template
NER_PROMPT = """Extract named entities from each article.

For each article, identify:
- ORG: Companies, organizations (e.g. Google, Microsoft, OpenAI)
- PRODUCT: Product names, model names (e.g. Gemma 4, GPT-5, vLLM)
- PERSON: Notable people (e.g. Sam Altman, Jensen Huang)
- EVENT: Events (e.g. Google I/O, NeurIPS)

Return JSON array:
[
  {
    "id": "article_id",
    "entities": [
      {"name": "Google", "type": "ORG", "normalized": "google"},
      {"name": "Gemma 4", "type": "PRODUCT", "normalized": "google_gemma_4"}
    ]
  }
]

Articles:
{articles_block}

JSON:"""
```

**Normalization Rules:**

```python
def normalize_entity(name: str, type: str) -> str:
    """Normalize entity name to lowercase underscore slug."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s-]+", "_", s)
    return s

# Examples:
# "Google Gemma 4" → "google_gemma_4"
# "gemma-4" → "gemma_4"
# "OpenAI" → "openai"
```

**Fallback:** If NER batch fails for an article, use `feed_id` as entity group.

---

### 5.3 Entity Clusterer — `src/application/report/entity_cluster.py`

**Responsibility:** Group articles by entity, classify into dimensions, generate headline.

**Class:** `EntityClusterer`

```python
class EntityClusterer:
    def __init__(
        self,
        large_event_threshold: int = 50,
        max_dimensions: int = 5,
    ):
        ...

    async def cluster(
        self, articles: list[ArticleEnriched], target_lang: str
    ) -> list[EntityTopic]:
        """Main entry: articles → entity topics."""
        ...

    def _group_by_entity(
        self, articles: list[ArticleEnriched]
    ) -> dict[str, list[ArticleEnriched]]:
        """Group articles by normalized entity_id."""
        ...

    def _classify_dimension(
        self, article: ArticleEnriched
    ) -> list[str]:
        """Classify article into one or more dimensions by keyword matching."""
        ...

    async def _generate_entity_topic(
        self, entity_id: str, articles: list[ArticleEnriched], target_lang: str
    ) -> EntityTopic:
        """Single LLM call per entity: headline + signals + layer."""
        ...
```

**LLM Chain:** `get_entity_topic_chain()` (extends existing pattern from `get_topic_title_and_layer_chain`):

```python
# Returns structured JSON
{
  "headline": "Google Gemma 4 开源：性能超越Llama 3 8B",
  "layer": "AI模型",
  "signals": ["开源", "SOTA", "多模态", "MIT许可证"],
  "insight": "Gemma 4以MIT许可证开源，在MMLU上超越Llama 3 8B..."
}
```

**Large Event Split:** If `articles_count > large_event_threshold`:
- Split `dimensions` into separate sub-entries
- Each sub-entry becomes its own `EntityTopic` with `parent_id` set
- e.g. "Google Gemma 4 (release)" and "Google Gemma 4 (research)" as two entries

---

### 5.4 TLDR Generator — `src/application/report/tldr.py`

**Responsibility:** Generate 1-sentence TLDR for top 10 entities.

**Class:** `TLDRGenerator`

```python
class TLDRGenerator:
    async def generate_top10(
        self, entity_topics: list[EntityTopic], target_lang: str
    ) -> list[EntityTopic]:
        """Take top 10 by quality_weight, generate tldr in-place."""
        ...
```

**LLM Chain:** `get_tldr_chain()` — single call:

```python
# Prompt
TLDR_PROMPT = """Generate a 1-sentence TLDR for each entity topic.
Focus on: what happened, why it matters.

Entity Topics:
{topics_block}

Return JSON array:
[
  {"entity_id": "google_gemma_4", "tldr": "Gemma 4以MIT许可证开源，在MMLU基准上超越Llama 3..."},
  ...
]

JSON:"""
```

---

### 5.5 Renderer — `src/application/report/render.py`

**Responsibility:** Render `ReportData` to Jinja2 template.

**Changes from current `report.py`:**
- Rename current `render_report()` → `render_thematic_report()`
- New `render_entity_report()` takes `ReportData` with entity topics
- Template `entity.md` replaces `v2.md` (or new template)

**Template sections:**

```markdown
# AI Daily Report — {{ date_range.since }} to {{ date_range.until }}

## Today's Top 10 AI News
{% for topic in tldr_top10 %}
{{ loop.index }}. {{ topic.headline }} [{{ topic.articles_count }}篇]
    {{ topic.tldr }}
{% endfor %}

## By Layer
{% for layer_name, topics in by_layer.items() %}
### {{ layer_name }} ({{ topics | sumattr('articles_count') }}篇, {{ topics | length }}个话题)
{% for topic in topics %}
#### {{ topic.entity_name }} ({{ topic.articles_count }}篇)
{{ topic.headline }}
{{ topic.tldr }}
**信号:** {{ topic.signals | join(", ") }}
{% endfor %}
{% endfor %}

## By Dimension
{% for dim_name, topics in by_dimension.items() %}
### {{ dim_name | dim_zh }} ({{ topics | length }}个话题)
...
{% endfor %}
```

---

## 6. LLM Chains — New Chains in `chains.py`

### 6.1 `get_ner_chain()`

```python
def get_ner_chain():
    from langchain.prompts import PromptTemplate
    from src.llm.core import llm_complete

    prompt = PromptTemplate.from_template(NER_PROMPT)
    chain = prompt | llm_complete
    return chain
```

### 6.2 `get_entity_topic_chain()`

```python
def get_entity_topic_chain():
    """Combined entity topic: headline + layer + signals (JSON output)."""
    # Reuses pattern from get_topic_title_and_layer_chain
    # Returns: {"headline": "...", "layer": "...", "signals": [...], "insight": "..."}
```

### 6.3 `get_tldr_chain()`

```python
def get_tldr_chain():
    """Generate TLDR for multiple entity topics at once (batch)."""
```

---

## 7. Pipeline Orchestration — `report.py`

**New async pipeline** replaces `_cluster_articles_async()`:

```python
async def _entity_report_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
) -> ReportData:
    """New entity-based report pipeline."""

    # Layer 0: Signal Filter
    signal_filter = SignalFilter()
    filtered = signal_filter.filter(pre_fetched_articles)

    # Layer 1: NER + Enrich
    ner = NERExtractor(batch_size=10)
    enriched = await ner.extract_batch(filtered)

    # Layer 2: Entity Clustering
    clusterer = EntityClusterer()
    entity_topics = await clusterer.cluster(enriched, target_lang)

    # Layer 3: TLDR Generation
    tldr_gen = TLDRGenerator()
    tldr_top10 = await tldr_gen.generate_top10(entity_topics, target_lang)

    # Group for render
    by_layer = group_by_layer(entity_topics)
    by_dimension = group_by_dimension(entity_topics)
    deep_dive = [t for t in entity_topics if t.articles_count > 50]

    return ReportData(
        tldr_top10=tldr_top10,
        by_layer=by_layer,
        by_dimension=by_dimension,
        deep_dive=deep_dive,
        date_range={"since": since, "until": until},
        target_lang=target_lang,
    )
```

**Existing CLI entry point** `cluster_articles_for_report()` calls `_entity_report_async()` instead of `_cluster_articles_async()`. No CLI changes required.

---

## 8. Backward Compatibility & Migration

### 8.1 Template Compatibility

Existing templates (`v2.md`, `default.md`) work with thematic clustering. New `entity.md` template works with entity clustering. The renderer selects template based on a new config flag:

```python
# In config or CLI
--report-mode entity|thematic  # default: entity
```

### 8.2 Thematic Clustering (Fallback)

If entity clustering fails (NER all fail, or < 3 entities found), fall back to existing thematic clustering:

```python
async def _entity_report_async(...):
    try:
        # ... entity pipeline ...
    except EntityClusterError:
        logger.warning("Entity clustering failed, falling back to thematic")
        return await _cluster_articles_async(...)  # existing pipeline
```

### 8.3 Feature Flags

Config in `config.py`:

```python
class ReportConfig:
    report_mode: str = "entity"  # "entity" | "thematic"
    ner_batch_size: int = 10
    quality_threshold: float = 0.6
    feed_weight_threshold: float = 0.5
    large_event_threshold: int = 50
    tldr_top_n: int = 10
```

---

## 9. Error Handling

| Error | Handling |
|-------|----------|
| NER batch fails | Log warning, use `feed_id` as entity fallback for failed articles |
| Entity clustering fails | Fall back to thematic clustering |
| TLDR generation fails | Leave `tldr` empty string, continue |
| Template not found | Fall back to `default.md` |
| All LLM calls fail | Raise `ReportGenerationError` with partial results |

---

## 10. File Structure Changes

```
src/application/report/
├── __init__.py              # Exports: generate_entity_report, SignalFilter, NERExtractor, etc.
├── report.py                # CLI entry + async orchestrator (refactored)
├── filter.py                # NEW: SignalFilter
├── ner.py                   # NEW: NERExtractor
├── entity_cluster.py         # NEW: EntityClusterer
├── tldr.py                   # NEW: TLDRGenerator
├── thematic.py              # RENAME: existing _cluster_articles_async (kept as fallback)
└── render.py                # NEW: render functions for entity mode

src/llm/
├── chains.py               # ADD: get_ner_chain, get_entity_topic_chain, get_tldr_chain
└── core.py                 # ADD: batch_ner_articles (if standalone needed)
```

---

## 11. Testing Strategy

### Unit Tests

| Component | Test |
|-----------|------|
| `SignalFilter` | test_quality_threshold, test_feed_weight, test_dedup |
| `NERExtractor` | test_normalize, test_batch_ner, test_fallback |
| `EntityClusterer` | test_group_by_entity, test_dimension_classify, test_large_event_split |
| `TLDRGenerator` | test_top10_ranking, test_tldr_format |

### Integration Tests

| Test | Description |
|------|-------------|
| `test_entity_report_pipeline` | Full run with mock LLM responses |
| `test_fallback_to_thematic` | When NER fails, verify thematic is used |
| `test_cli_compatible` | `feedship report --since X --until Y` produces entity report |

---

## 12. Implementation Phases

**Phase 1: Foundation (独立可测)**
- `SignalFilter` — no LLM, pure rules
- `ner.py` + `get_ner_chain()`
- `filter.py` + `SignalFilter`

**Phase 2: Core Clustering**
- `entity_cluster.py` + `get_entity_topic_chain()`
- `tldr.py` + `get_tldr_chain()`
- New pipeline in `report.py`

**Phase 3: Rendering**
- `render.py` + `entity.md` template
- Backward compatibility with thematic fallback

**Phase 4: Polish & Config**
- Config flags in `config.py`
- CLI `--report-mode` flag
- Integration tests

---

## 13. Open Questions (to be resolved in implementation)

1. **NER model**: Use MiniMax with JSON output mode. If JSON mode unavailable, use regex parsing.
2. **Entity resolution ambiguity**: "Gemma" could be Google Gemma or other. NER prompt should specify to include parent org when ambiguous.
3. **Dimension classification**: Rule-based keyword matching for v1. Can be upgraded to LLM in future.
4. **TLDR language**: TLDR generated in target_lang (same as report language).
5. **Max entity count**: If > 50 entities found, rank by quality_weight and take top 50.

---

## 14. Appendix: LLM Call Count Comparison

| Pipeline | Articles | LLM Calls | Intelligence |
|----------|----------|-----------|--------------|
| Current thematic | 200 | ~192 | Thematic clusters |
| Current thematic | 3333 | ~730+ | Thematic clusters (many small) |
| **New entity** | 3333→300 | **~170** | **Entity clusters + TLDR** |
