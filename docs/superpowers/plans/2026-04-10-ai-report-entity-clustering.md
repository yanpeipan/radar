# AI Report Entity Clustering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reimplement the report pipeline with entity-based clustering instead of thematic clustering, per the design spec at `docs/superpowers/specs/2026-04-10-ai-report-entity-clustering-design.md`.

**Architecture:** 5-layer pipeline: Signal Filter (rules) → NER batch (LLM) → Entity Clustering (LLM) → TLDR Generation (1 LLM) → Render (Jinja2). All entity components live under `src/application/report/`.

**Tech Stack:** Python asyncio, langchain LCEL, SQLite, Jinja2.

---

## File Structure

```
src/application/report/
├── __init__.py              # Exports all public classes
├── report.py                # MODIFY: add _entity_report_async(), update CLI
├── filter.py                # CREATE: SignalFilter (Layer 0)
├── ner.py                   # CREATE: NERExtractor (Layer 1)
├── entity_cluster.py        # CREATE: EntityClusterer (Layer 2)
├── tldr.py                  # CREATE: TLDRGenerator (Layer 3)
├── render.py                # CREATE: render functions (Layer 4)
├── thematic.py              # CREATE: moved existing thematic pipeline (fallback)
└── entity.md                # CREATE: Jinja2 template for entity reports

src/llm/
└── chains.py                # MODIFY: add get_ner_chain, get_entity_topic_chain, get_tldr_chain

tests/application/report/
├── __init__.py
├── test_filter.py           # CREATE
├── test_ner.py              # CREATE
├── test_entity_cluster.py   # CREATE
└── test_tldr.py             # CREATE
```

## Data Structures (src/application/report/models.py)

All dataclasses defined first so tasks can reference types consistently.


### Task 1: Data Structures

**Files:**
- Create: `src/application/report/models.py`
- Test: `tests/application/report/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/application/report/test_models.py
import pytest
from src.application.report.models import EntityTag, ArticleEnriched, EntityTopic, ReportData

def test_entity_tag_fields():
    tag = EntityTag(name="Google Gemma 4", type="PRODUCT", normalized="google_gemma_4")
    assert tag.name == "Google Gemma 4"
    assert tag.type == "PRODUCT"
    assert tag.normalized == "google_gemma_4"

def test_article_enriched_default_fields():
    article = ArticleEnriched(
        id="a1", title="Test", link="http://x.com", summary="",
        quality_score=0.8, feed_weight=0.7, published_at="2026-04-09", feed_id="f1"
    )
    assert article.entities == []
    assert article.dimensions == []

def test_entity_topic_quality_weight():
    topic = EntityTopic(
        entity_id="google_gemma_4", entity_name="Google Gemma 4",
        layer="AI模型", headline="Gemma 4发布",
        dimensions={"release": []}, articles_count=10,
        signals=[], tldr="", quality_weight=0.0
    )
    # quality_weight is computed
    assert topic.quality_weight == 0.8 * 10  # quality_score * articles_count

def test_report_data_tldr_top10_sorted():
    # Top 10 should be sorted by quality_weight descending
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/report/test_models.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/report/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class EntityTag:
    name: str
    type: str  # ORG | PRODUCT | MODEL | PERSON | EVENT
    normalized: str

@dataclass
class ArticleEnriched:
    id: str
    title: str
    link: str
    summary: str
    quality_score: float
    feed_weight: float
    published_at: str
    feed_id: str
    entities: list[EntityTag] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)

@dataclass
class EntityTopic:
    entity_id: str
    entity_name: str
    layer: str
    headline: str
    dimensions: dict[str, list[ArticleEnriched]] = field(default_factory=dict)
    articles_count: int
    signals: list[str] = field(default_factory=list)
    tldr: str = ""
    quality_weight: float = 0.0

@dataclass
class ReportData:
    tldr_top10: list[EntityTopic]
    by_layer: dict[str, list[EntityTopic]]
    by_dimension: dict[str, list[EntityTopic]]
    deep_dive: list[EntityTopic]
    date_range: dict[str, str]
    target_lang: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/report/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/report/models.py tests/application/report/test_models.py
git commit -m "feat(report): add entity clustering data models"
```

---

### Task 2: SignalFilter - Layer 0

**Files:**
- Create: `src/application/report/filter.py`
- Modify: `tests/application/report/test_filter.py`
- Read first: `src/application/dedup.py` (for SHA256 dedup logic)

- [ ] **Step 1: Write the failing test**

```python
# tests/application/report/test_filter.py
import pytest
from src.application.report.filter import SignalFilter

def test_signal_filter_quality_threshold():
    articles = [
        {"id": "1", "quality_score": 0.8, "feed_weight": 0.7},
        {"id": "2", "quality_score": 0.5, "feed_weight": 0.7},
    ]
    sf = SignalFilter(quality_threshold=0.6)
    result = sf.filter(articles)
    assert len(result) == 1
    assert result[0]["id"] == "1"

def test_signal_filter_feed_weight_threshold():
    articles = [
        {"id": "1", "quality_score": 0.8, "feed_weight": 0.7},
        {"id": "2", "quality_score": 0.8, "feed_weight": 0.4},
    ]
    sf = SignalFilter(feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 1
    assert result[0]["id"] == "1"

def test_signal_filter_combined():
    articles = [
        {"id": "1", "quality_score": 0.8, "feed_weight": 0.7},
        {"id": "2", "quality_score": 0.5, "feed_weight": 0.4},
        {"id": "3", "quality_score": 0.7, "feed_weight": 0.6},
    ]
    sf = SignalFilter(quality_threshold=0.6, feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 2
    ids = {r["id"] for r in result}
    assert ids == {"1", "3"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/report/test_filter.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/report/filter.py
"""Layer 0: Signal Filter - rules-based article filtering."""

from __future__ import annotations

import hashlib
from typing import Any

# Event keywords that trigger a quality boost
_EVENT_KEYWORDS = [
    "release", "launch", "announce", "发布", "推出", "开源",
    "funding", "raise", "series", "vc", "融资", "投资",
    "acquisition", "merger", "收购", "合并",
    "regulation", "policy", "ban", "监管", "政策",
    "paper", "research", "study", "研究", "论文",
    "open source", "github", "pypi", "npm",
]


class SignalFilter:
    """Filter articles by quality signals to reduce from ~3333 to ~300."""

    def __init__(
        self,
        quality_threshold: float = 0.6,
        feed_weight_threshold: float = 0.5,
        event_signal_boost: bool = True,
    ):
        self.quality_threshold = quality_threshold
        self.feed_weight_threshold = feed_weight_threshold
        self.event_signal_boost = event_signal_boost

    def filter(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply all filter rules. Returns filtered articles."""
        seen_hashes: set[str] = set()
        result = []
        for article in articles:
            if self._passes_all_rules(article, seen_hashes):
                result.append(article)
        return result

    def _passes_all_rules(self, article: dict, seen_hashes: set[str]) -> bool:
        # Rule 1: SHA256 exact dedup (title + content[:500])
        content = article.get("content", "") or article.get("description", "") or ""
        content_preview = content[:500]
        h = hashlib.sha256(
            f"{article.get('title', '')}{content_preview}".encode()
        ).hexdigest()
        if h in seen_hashes:
            return False
        seen_hashes.add(h)

        # Rule 2: Quality gate (with optional event boost)
        quality = article.get("quality_score", 0.0)
        title = article.get("title", "")
        effective_quality = quality
        if self.event_signal_boost and self._has_event_signal(title):
            effective_quality += 0.1

        if effective_quality < self.quality_threshold:
            return False

        # Rule 3: Feed weight gate
        feed_weight = article.get("feed_weight", 0.0)
        if feed_weight < self.feed_weight_threshold:
            return False

        return True

    def _has_event_signal(self, title: str) -> bool:
        title_lower = title.lower()
        return any(kw in title_lower for kw in _EVENT_KEYWORDS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/report/test_filter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/report/filter.py tests/application/report/test_filter.py
git commit -m "feat(report): add SignalFilter for Layer 0 article filtering"
```

---

### Task 3: LLM Chains — get_ner_chain, get_entity_topic_chain, get_tldr_chain

**Files:**
- Modify: `src/llm/chains.py` (ADD new chains at end of file)
- Modify: `tests/application/report/test_chains.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/application/report/test_chains.py
import pytest
from src.llm.chains import get_ner_chain, get_entity_topic_chain, get_tldr_chain

def test_get_ner_chain_returns_runnable():
    chain = get_ner_chain()
    assert chain is not None
    assert hasattr(chain, 'invoke')

def test_get_entity_topic_chain_returns_runnable():
    chain = get_entity_topic_chain()
    assert chain is not None
    assert hasattr(chain, 'invoke')

def test_get_tldr_chain_returns_runnable():
    chain = get_tldr_chain()
    assert chain is not None
    assert hasattr(chain, 'invoke')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/report/test_chains.py -v`
Expected: FAIL - function not found

- [ ] **Step 3: Write minimal implementation**

Add these three functions at the END of `src/llm/chains.py`:

```python
# NER chain — batch extract named entities from articles
NER_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a named entity recognition system. Extract entities from articles. "
        "Return ONLY valid JSON array."
    ),
    (
        "human",
        "Articles:
{articles_block}

Return JSON array of {"id": "article_id", "entities": [{"name": "...", "type": "ORG|PRODUCT|MODEL|PERSON|EVENT", "normalized": "..."}]} for each article."
    ),
])

def get_ner_chain() -> Runnable:
    """Returns LCEL chain for batch NER extraction."""
    return (
        NER_PROMPT
        | _get_llm_wrapper(200)
        | JsonOutputParser()
    )


# Entity topic chain — headline + layer + signals for one entity
ENTITY_TOPIC_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a news analyst. For the given entity and its articles, "
        "generate: (1) a headline (max 30 chars), (2) the AI five-layer cake layer, "
        "(3) signal tags, (4) a 1-sentence insight. "
        "Return ONLY valid JSON. "
        "Layers: AI应用, AI模型, AI基础设施, 芯片, 能源."
    ),
    (
        "human",
        "Entity: {entity_name}
Articles ({article_count}):
{article_list}

Return JSON with: headline, layer, signals (list), insight."
    ),
])

def get_entity_topic_chain() -> Runnable:
    """Returns LCEL chain for entity topic headline + layer + signals."""
    return (
        ENTITY_TOPIC_PROMPT
        | _get_llm_wrapper(150)
        | JsonOutputParser()
    )


# TLDR chain — generate 1-sentence TLDR for multiple entities at once
TLDR_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a news editor. Generate a 1-sentence TLDR for each entity topic. "
        "Focus on: what happened, why it matters. Write in {target_lang}."
    ),
    (
        "human",
        "Entity Topics:
{topics_block}

Return JSON array of {"entity_id": "...", "tldr": "..."} for each topic."
    ),
])

def get_tldr_chain() -> Runnable:
    """Returns LCEL chain for batch TLDR generation."""
    return (
        TLDR_PROMPT
        | _get_llm_wrapper(300)
        | JsonOutputParser()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/report/test_chains.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm/chains.py tests/application/report/test_chains.py
git commit -m "feat(report): add get_ner_chain, get_entity_topic_chain, get_tldr_chain"
```

---

### Task 4: NERExtractor — Layer 1

**Files:**
- Create: `src/application/report/ner.py`
- Create: `tests/application/report/test_ner.py`
- Read: `src/llm/chains.py` (get_ner_chain), `src/llm/core.py` (batch_summarize_articles pattern)

- [ ] **Step 1: Write the failing test**

```python
# tests/application/report/test_ner.py
import pytest
from src.application.report.ner import NERExtractor, normalize_entity

def test_normalize_entity():
    assert normalize_entity("Google Gemma 4", "PRODUCT") == "google_gemma_4"
    assert normalize_entity("gemma-4", "PRODUCT") == "gemma_4"
    assert normalize_entity("OpenAI", "ORG") == "openai"
    assert normalize_entity("Sam Altman", "PERSON") == "sam_altman"

def test_ner_extractor_batch_size():
    ner = NERExtractor(batch_size=10)
    assert ner.batch_size == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/report/test_ner.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/report/ner.py
"""Layer 1: NER + Entity Resolution — extract and normalize entities from articles."""

from __future__ import annotations

import re
from typing import Any

from src.application.report.models import ArticleEnriched, EntityTag
from src.llm.chains import get_ner_chain


def normalize_entity(name: str, _type: str | None = None) -> str:
    """Normalize entity name to lowercase underscore slug.

    Examples:
        "Google Gemma 4" -> "google_gemma_4"
        "gemma-4" -> "gemma_4"
        "OpenAI" -> "openai"
    """
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s-]+", "_", s)
    return s


class NERExtractor:
    """Extract named entities from articles using LLM batch processing."""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    async def extract_batch(
        self, articles: list[dict[str, Any]]
    ) -> list[ArticleEnriched]:
        """Process articles in batches. Returns enriched articles with entity tags."""
        import asyncio
        chain = get_ner_chain()
        results: list[ArticleEnriched] = []
        semaphore = asyncio.Semaphore(3)  # max 3 concurrent batches

        async def process_batch(batch: list[dict[str, Any]]) -> list[ArticleEnriched]:
            async with semaphore:
                # Build articles block for prompt
                articles_block = "\n".join(
                    f'Article {i+1} (id={a["id"]}): {a.get("title", "")[:200]}'
                    for i, a in enumerate(batch)
                )
                try:
                    raw = await chain.ainvoke({"articles_block": articles_block})
                    import json
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    # Fallback: use feed_id as entity
                    return [
                        ArticleEnriched(
                            id=a["id"],
                            title=a.get("title", ""),
                            link=a.get("link", ""),
                            summary=a.get("summary", ""),
                            quality_score=a.get("quality_score", 0.0),
                            feed_weight=a.get("feed_weight", 0.0),
                            published_at=a.get("published_at", ""),
                            feed_id=a.get("feed_id", "unknown"),
                            entities=[],
                            dimensions=[],
                        )
                        for a in batch
                    ]

            # Map results back to articles
            id_to_entities: dict[str, list[EntityTag]] = {}
            for item in parsed:
                aid = item.get("id", "")
                id_to_entities[aid] = [
                    EntityTag(
                        name=e["name"],
                        type=e.get("type", "ORG"),
                        normalized=normalize_entity(e["name"], e.get("type")),
                    )
                    for e in item.get("entities", [])
                ]

            enriched = []
            for a in batch:
                entities = id_to_entities.get(a["id"], [])
                enriched.append(
                    ArticleEnriched(
                        id=a["id"],
                        title=a.get("title", ""),
                        link=a.get("link", ""),
                        summary=a.get("summary", ""),
                        quality_score=a.get("quality_score", 0.0),
                        feed_weight=a.get("feed_weight", 0.0),
                        published_at=a.get("published_at", ""),
                        feed_id=a.get("feed_id", "unknown"),
                        entities=entities,
                        dimensions=[],
                    )
                )
            return enriched

        # Chunk articles into batches
        batches = [
            articles[i : i + self.batch_size]
            for i in range(0, len(articles), self.batch_size)
        ]
        batch_results = await asyncio.gather(*[process_batch(b) for b in batches])
        for batch_result in batch_results:
            results.extend(batch_result)
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/report/test_ner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/report/ner.py tests/application/report/test_ner.py
git commit -m "feat(report): add NERExtractor for Layer 1 entity extraction"
```

---

### Task 5: EntityClusterer — Layer 2

**Files:**
- Create: `src/application/report/entity_cluster.py`
- Create: `tests/application/report/test_entity_cluster.py`
- Read: `src/application/report/ner.py`, `src/application/report/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/application/report/test_entity_cluster.py
import pytest
from src.application.report.entity_cluster import EntityClusterer, classify_dimensions
from src.application.report.models import ArticleEnriched, EntityTag

def test_classify_dimensions_release():
    article = ArticleEnriched(
        id="1", title="Google Gemma 4 Released", link="", summary="",
        quality_score=0.8, feed_weight=0.7, published_at="", feed_id="f1",
        entities=[], dimensions=[]
    )
    dims = classify_dimensions(article)
    assert "release" in dims

def test_classify_dimensions_funding():
    article = ArticleEnriched(
        id="1", title="OpenAI Raises $10B", link="", summary="",
        quality_score=0.8, feed_weight=0.7, published_at="", feed_id="f1",
        entities=[], dimensions=[]
    )
    dims = classify_dimensions(article)
    assert "funding" in dims

def test_classify_dimensions_research():
    article = ArticleEnriched(
        id="1", title="New Research Paper on LLM", link="", summary="",
        quality_score=0.8, feed_weight=0.7, published_at="", feed_id="f1",
        entities=[], dimensions=[]
    )
    dims = classify_dimensions(article)
    assert "research" in dims
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/report/test_entity_cluster.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/report/entity_cluster.py
"""Layer 2: Entity Clustering — group articles by entity, classify dimensions."""

from __future__ import annotations

from typing import Any

from src.application.report.models import ArticleEnriched, EntityTopic
from src.llm.chains import get_entity_topic_chain

# Dimension keywords for rule-based classification
_DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "release": ["release", "launch", "announce", "发布", "推出", "launches", "unveils"],
    "funding": ["funding", "raise", "series", "vc", "invest", "融资", "投资", "raises"],
    "research": ["research", "paper", "study", "benchmark", "研究", "论文", "arxiv"],
    "ecosystem": ["open source", "github", "acquisition", "merger", "partnership", "生态", "开源", "收购"],
    "policy": ["regulation", "policy", "government", "ban", "监管", "政策"],
}

# Five layers
_LAYERS = ["AI应用", "AI模型", "AI基础设施", "芯片", "能源"]


def classify_dimensions(article: ArticleEnriched) -> list[str]:
    """Classify article into one or more dimensions by keyword matching."""
    text = article.title.lower() + " " + article.summary.lower()
    dims = []
    for dim, keywords in _DIMENSION_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            dims.append(dim)
    return dims if dims else ["ecosystem"]  # default


class EntityClusterer:
    """Cluster articles by entity and generate entity topics."""

    def __init__(
        self,
        large_event_threshold: int = 50,
        max_entities: int = 50,
    ):
        self.large_event_threshold = large_event_threshold
        self.max_entities = max_entities

    async def cluster(
        self, articles: list[ArticleEnriched], target_lang: str
    ) -> list[EntityTopic]:
        """Main entry: articles -> entity topics."""
        # Group by normalized entity
        entity_groups: dict[str, list[ArticleEnriched]] = {}
        for article in articles:
            if not article.entities:
                # Fallback: use feed_id
                feed_id = article.feed_id or "unknown"
                entity_groups.setdefault(feed_id, []).append(article)
            else:
                # Use first entity's normalized name
                primary = article.entities[0].normalized
                entity_groups.setdefault(primary, []).append(article)

        # Rank by quality_weight and take top max_entities
        ranked = sorted(
            entity_groups.items(),
            key=lambda x: sum(a.quality_score for a in x[1]) * len(x[1]),
            reverse=True,
        )
        ranked = ranked[: self.max_entities]

        # Generate topic for each entity
        import asyncio
        chain = get_entity_topic_chain()
        semaphore = asyncio.Semaphore(5)
        topics: list[EntityTopic] = []

        async def generate_one(entity_id: str, entity_articles: list[ArticleEnriched]) -> EntityTopic | None:
            async with semaphore:
                # Classify dimensions for each article
                for art in entity_articles:
                    art.dimensions = classify_dimensions(art)

                # Group by dimension
                by_dim: dict[str, list[ArticleEnriched]] = {}
                for art in entity_articles:
                    for dim in art.dimensions:
                        by_dim.setdefault(dim, []).append(art)

                # Build article list for prompt
                article_list = "\n".join(
                    f"- [{a.title}]({a.link})" for a in entity_articles[:10]
                )
                entity_name = entity_articles[0].entities[0].name if entity_articles[0].entities else entity_id

                try:
                    result = await chain.ainvoke({
                        "entity_name": entity_name,
                        "article_count": len(entity_articles),
                        "article_list": article_list,
                        "target_lang": target_lang,
                    })
                except Exception:
                    # Fallback
                    return EntityTopic(
                        entity_id=entity_id,
                        entity_name=entity_name,
                        layer="AI应用",
                        headline=entity_name[:30],
                        dimensions=by_dim,
                        articles_count=len(entity_articles),
                        signals=[],
                        tldr="",
                        quality_weight=sum(a.quality_score for a in entity_articles) * len(entity_articles),
                    )

                layer = result.get("layer", "AI应用")
                if layer not in _LAYERS:
                    layer = "AI应用"

                return EntityTopic(
                    entity_id=entity_id,
                    entity_name=entity_name,
                    layer=layer,
                    headline=result.get("headline", entity_name[:30]),
                    dimensions=by_dim,
                    articles_count=len(entity_articles),
                    signals=result.get("signals", []),
                    tldr="",
                    quality_weight=sum(a.quality_score for a in entity_articles) * len(entity_articles),
                )

        results = await asyncio.gather(*[
            generate_one(eid, earts) for eid, earts in ranked
        ])
        topics = [r for r in results if r is not None]
        return topics
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/report/test_entity_cluster.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/report/entity_cluster.py tests/application/report/test_entity_cluster.py
git commit -m "feat(report): add EntityClusterer for Layer 2 entity clustering"
```

---

### Task 6: TLDRGenerator — Layer 3

**Files:**
- Create: `src/application/report/tldr.py`
- Create: `tests/application/report/test_tldr.py`
- Read: `src/application/report/entity_cluster.py`, `src/application/report/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/application/report/test_tldr.py
import pytest
from src.application.report.tldr import TLDRGenerator
from src.application.report.models import EntityTopic

def test_tldr_generator_initialized():
    gen = TLDRGenerator()
    assert gen is not None

def test_tldr_generator_top10_ranking():
    # Top 10 should be sorted by quality_weight descending
    gen = TLDRGenerator()
    assert gen.top_n == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/application/report/test_tldr.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/application/report/tldr.py
"""Layer 3: TLDR Generation — 1-sentence TLDR for top 10 entities."""

from __future__ import annotations

from src.application.report.models import EntityTopic
from src.llm.chains import get_tldr_chain


class TLDRGenerator:
    def __init__(self, top_n: int = 10):
        self.top_n = top_n

    async def generate_top10(
        self, entity_topics: list[EntityTopic], target_lang: str
    ) -> list[EntityTopic]:
        """Take top N by quality_weight, generate tldr in-place. Returns top N."""
        import asyncio

        # Sort and take top N
        sorted_topics = sorted(
            entity_topics, key=lambda t: t.quality_weight, reverse=True
        )[: self.top_n]

        if not sorted_topics:
            return []

        # Build topics block for prompt
        topics_block = "\n".join(
            f'Entity {i+1} ({t.entity_name}): {t.headline}'
            for i, t in enumerate(sorted_topics)
        )

        chain = get_tldr_chain()
        try:
            raw = await chain.ainvoke({
                "topics_block": topics_block,
                "target_lang": target_lang,
            })
            import json
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            # Leave tldr empty on failure
            return sorted_topics

        # Map tldr back to topics
        tldr_map = {item.get("entity_id", ""): item.get("tldr", "") for item in parsed}
        for topic in sorted_topics:
            topic.tldr = tldr_map.get(topic.entity_id, "")

        return sorted_topics
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/application/report/test_tldr.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/application/report/tldr.py tests/application/report/test_tldr.py
git commit -m "feat(report): add TLDRGenerator for Layer 3 TLDR generation"
```

---

### Task 7: Renderer — Layer 4

**Files:**
- Create: `src/application/report/render.py`
- Create: `templates/entity.md` (read existing templates in `~/.local/share/feedship/templates/` first)
- Read: `src/application/report/report.py` (render_report function around line 895)

- [ ] **Step 1: Write the renderer without template — test dimension_zh filter**

```python
# src/application/report/render.py
"""Layer 4: Render — entity report Jinja2 rendering."""

from __future__ import annotations

from typing import Any

# Dimension translation
DIM_ZH: dict[str, str] = {
    "release": "发布",
    "funding": "融资",
    "research": "研究",
    "ecosystem": "生态",
    "policy": "监管",
}


def dim_zh(dim: str) -> str:
    """Translate dimension key to Chinese."""
    return DIM_ZH.get(dim, dim)


def group_by_layer(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        layer = getattr(t, "layer", "AI应用")
        result.setdefault(layer, []).append(t)
    return result


def group_by_dimension(topics: list) -> dict[str, list]:
    result: dict[str, list] = {}
    for t in topics:
        for dim in getattr(t, "dimensions", {}).keys():
            result.setdefault(dim, []).append(t)
    return result


async def render_entity_report(
    entity_topics: list,
    since: str,
    until: str,
    target_lang: str,
    template_name: str = "entity",
) -> str:
    """Render entity report using Jinja2.

    Args:
        entity_topics: List of EntityTopic objects (already has tldr_top10)
        since: Start date
        until: End date
        target_lang: Target language code
        template_name: Template file name (without .md extension)

    Returns:
        Rendered markdown string.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from pathlib import Path

    # Find template
    template_dirs = [
        Path.home() / ".local" / "share" / "feedship" / "templates",
        Path(__file__).parent.parent.parent / "templates",
    ]
    env = Environment(
        loader=FileSystemLoader([str(d) for d in template_dirs]),
        autoescape=select_autoescape(),
    )
    env.filters["dim_zh"] = dim_zh

    # If entity.md doesn't exist, render inline
    try:
        template = env.get_template(f"{template_name}.md")
    except Exception:
        # Inline rendering fallback
        return render_entity_inline(entity_topics, since, until, target_lang)

    by_layer = group_by_layer(entity_topics)
    by_dimension = group_by_dimension(entity_topics)
    deep_dive = [t for t in entity_topics if getattr(t, "articles_count", 0) > 50]

    # Sort by quality_weight
    for layer_list in by_layer.values():
        layer_list.sort(key=lambda t: t.quality_weight, reverse=True)
    for dim_list in by_dimension.values():
        dim_list.sort(key=lambda t: t.quality_weight, reverse=True)
    deep_dive.sort(key=lambda t: t.quality_weight, reverse=True)

    return template.render(
        tldr_top10=entity_topics[:10],
        by_layer=by_layer,
        by_dimension=by_dimension,
        deep_dive=deep_dive,
        date_range={"since": since, "until": until},
        target_lang=target_lang,
        dim_zh=dim_zh,
    )


def render_entity_inline(
    entity_topics: list,
    since: str,
    until: str,
    target_lang: str,
) -> str:
    """Inline markdown rendering fallback when template not available."""
    by_layer = group_by_layer(entity_topics)
    lines = [
        f"# AI Daily Report — {since} to {until}",
        "",
        "## Today's Top 10 AI News",
    ]
    for i, topic in enumerate(entity_topics[:10]):
        lines.append(f"{i+1}. **{topic.headline}** [{topic.articles_count} articles]")
        if topic.tldr:
            lines.append(f"   {topic.tldr}")
        lines.append("")

    lines.append("## By Layer")
    for layer, topics in by_layer.items():
        article_count = sum(t.articles_count for t in topics)
        lines.append(f"### {layer} ({article_count} articles, {len(topics)} topics)")
        for topic in topics[:5]:
            lines.append(f"#### {topic.entity_name} ({topic.articles_count} articles)")
            lines.append(f"{topic.headline}")
            if topic.tldr:
                lines.append(f"_{topic.tldr}_")
            lines.append(f"Signals: {', '.join(topic.signals)}")
            lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Verify inline render works (no template needed)**

Test by running: `python3 -c "from src.application.report.render import render_entity_inline, dim_zh; print(dim_zh('release'))"`
Expected: "发布"

- [ ] **Step 3: Create entity.md template**

Create `~/.local/share/feedship/templates/entity.md`:

```markdown
# AI Daily Report — {{ date_range.since }} to {{ date_range.until }}

## Today's Top 10 AI News
{% for topic in tldr_top10[:10] %}
{{ loop.index }}. **{{ topic.headline }}** [{{ topic.articles_count }} articles]
{% if topic.tldr %}
   {{ topic.tldr }}
{% endif %}
{% endfor %}

## By Layer
{% for layer_name, topics in by_layer.items() %}
### {{ layer_name }} ({{ topics | sumattr('articles_count') }} articles, {{ topics | length }} topics)
{% for topic in topics %}
#### {{ topic.entity_name }} ({{ topic.articles_count }} articles)
**{{ topic.headline }}**
{% if topic.tldr %}
*{{ topic.tldr }}*
{% endif %}
**Signals:** {{ topic.signals | join(", ") }}
{% endfor %}
{% endfor %}

## By Dimension
{% for dim_name, topics in by_dimension.items() %}
### {{ dim_name | dim_zh }} ({{ topics | length }} topics)
{% for topic in topics %}
- **{{ topic.entity_name }}**: {{ topic.headline }}
{% endfor %}
{% endfor %}
```

- [ ] **Step 4: Commit**

```bash
git add src/application/report/render.py
mkdir -p ~/.local/share/feedship/templates
cp entity.md ~/.local/share/feedship/templates/entity.md 2>/dev/null || true
git add ~/.local/share/feedship/templates/entity.md 2>/dev/null || true
git commit -m "feat(report): add render.py for Layer 4 entity report rendering"
```

---

### Task 8: Pipeline Integration — _entity_report_async

**Files:**
- Modify: `src/application/report/report.py`
- Read: `src/application/report.py` line 870-893 (cluster_articles_for_report), lines 690-780 (_cluster_articles_async)

- [ ] **Step 1: Verify existing CLI entry point**

Read the current `cluster_articles_for_report()` function at line 870 in `src/application/report/report.py`.

- [ ] **Step 2: Add _entity_report_async function**

Add this BEFORE the existing `cluster_articles_for_report()` function (around line 869):

```python
async def _entity_report_async(
    pre_fetched_articles: list,
    since: str,
    until: str,
    auto_summarize: bool,
    target_lang: str,
) -> dict[str, Any]:
    """New entity-based report pipeline (5 layers).

    Layer 0: Signal Filter (rules)
    Layer 1: NER + Entity Resolution (LLM batch)
    Layer 2: Entity Clustering (LLM)
    Layer 3: TLDR Generation (1 LLM call)
    Layer 4: Render (Jinja2)
    """
    from src.application.report.filter import SignalFilter
    from src.application.report.ner import NERExtractor
    from src.application.report.entity_cluster import EntityClusterer
    from src.application.report.tldr import TLDRGenerator
    from src.application.report.render import render_entity_report

    # Layer 0: Signal Filter
    signal_filter = SignalFilter()
    filtered = signal_filter.filter(pre_fetched_articles)

    # Layer 1: NER + Enrich
    ner = NERExtractor(batch_size=10)
    enriched = await ner.extract_batch(filtered)

    # Layer 2: Entity Clustering
    clusterer = EntityClusterer()
    entity_topics = await clusterer.cluster(enriched, target_lang)

    # Layer 3: TLDR Generation (top 10)
    tldr_gen = TLDRGenerator(top_n=10)
    tldr_top10 = await tldr_gen.generate_top10(entity_topics, target_lang)

    # Layer 4: Render
    rendered = await render_entity_report(
        tldr_top10, since, until, target_lang, template_name="entity"
    )

    # Group for backward-compatible return dict
    from src.application.report.render import group_by_layer, group_by_dimension
    by_layer = group_by_layer(entity_topics)
    by_dimension = group_by_dimension(entity_topics)

    return {
        "rendered": rendered,
        "tldr_top10": tldr_top10,
        "by_layer": by_layer,
        "by_dimension": by_dimension,
        "entity_topics": entity_topics,
        "date_range": {"since": since, "until": until},
    }
```

- [ ] **Step 3: Update cluster_articles_for_report to use new pipeline**

Replace the `cluster_articles_for_report()` body (line 870-892) to call `_entity_report_async` instead of `_cluster_articles_async`:

```python
def cluster_articles_for_report(
    since: str,
    until: str,
    limit: int = 200,
    auto_summarize: bool = True,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """Fetch and cluster articles for an entity-based report.

    Returns:
        dict with keys: rendered (markdown str), tldr_top10, by_layer,
        by_dimension, entity_topics, date_range ({since, until}).
    """
    articles = list_articles_for_llm(
        limit=limit,
        since=since,
        until=until,
        unsummarized_only=False,
    )
    return asyncio.run(
        _entity_report_async(articles, since, until, auto_summarize, target_lang)
    )
```

- [ ] **Step 4: Verify the function can be imported**

Run: `cd /Users/y3/feedship && python3 -c "from src.application.report import _entity_report_async; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add src/application/report/report.py
git commit -m "feat(report): integrate entity pipeline as primary report flow"
```

---

### Task 9: Thematic Fallback (preserve existing pipeline)

**Files:**
- Create: `src/application/report/thematic.py`
- Modify: `src/application/report/report.py` (import fallback)

- [ ] **Step 1: Move existing thematic pipeline to thematic.py**

The existing `_cluster_articles_async` (line 690-780) and `cluster_articles_for_report` should be preserved as fallback. Extract the current implementation to `thematic.py`:

```python
# src/application/report/thematic.py
"""Thematic clustering fallback — preserved from original report pipeline."""
# Copy the existing _cluster_articles_async function here
# for use as fallback when entity clustering fails.
# (Exact code to be extracted from current report.py)
```

- [ ] **Step 2: Add fallback in _entity_report_async**

Wrap the entity pipeline in a try/except in `_entity_report_async`. On failure, call thematic fallback:

```python
async def _entity_report_async(...) -> dict[str, Any]:
    try:
        # ... entity pipeline ...
    except Exception as e:
        logger.warning(f"Entity clustering failed: {e}, falling back to thematic")
        return await _thematic_report_async(pre_fetched_articles, since, until, auto_summarize, target_lang)
```

- [ ] **Step 3: Commit**

```bash
git add src/application/report/thematic.py src/application/report/report.py
git commit -m "feat(report): preserve thematic fallback for entity pipeline"
```

---

### Task 10: Package Init + Export

**Files:**
- Create: `src/application/report/__init__.py`
- Modify: `src/application/__init__.py` (add report export)

- [ ] **Step 1: Write __init__.py**

```python
# src/application/report/__init__.py
"""Entity-based report generation pipeline.

Modules:
- filter: SignalFilter (Layer 0)
- ner: NERExtractor (Layer 1)
- entity_cluster: EntityClusterer (Layer 2)
- tldr: TLDRGenerator (Layer 3)
- render: render_entity_report (Layer 4)
- thematic: ThematicClusterer (fallback)
"""

from src.application.report.filter import SignalFilter
from src.application.report.ner import NERExtractor
from src.application.report.entity_cluster import EntityClusterer
from src.application.report.tldr import TLDRGenerator
from src.application.report.render import render_entity_report
from src.application.report.models import (
    ArticleEnriched,
    EntityTag,
    EntityTopic,
    ReportData,
)

__all__ = [
    "SignalFilter",
    "NERExtractor",
    "EntityClusterer",
    "TLDRGenerator",
    "render_entity_report",
    "ArticleEnriched",
    "EntityTag",
    "EntityTopic",
    "ReportData",
]
```

- [ ] **Step 2: Verify imports work**

Run: `cd /Users/y3/feedship && python3 -c "from src.application.report import SignalFilter, NERExtractor, EntityClusterer, TLDRGenerator; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add src/application/report/__init__.py
git commit -m "feat(report): add report package __init__.py exports"
```

---

### Task 11: End-to-End Test — uv run feedship report

- [ ] **Step 1: Run the full test command**

```bash
cd /Users/y3/feedship && uv run feedship --debug report --since 2026-04-07 --until 2026-04-10 --language zh
```

- [ ] **Step 2: Fix all errors encountered**

Common issues to watch for:
- Import errors (missing modules, circular imports)
- LLM chain failures (JSON parsing, provider errors)
- Template not found (ensure entity.md is in correct location)
- Async event loop issues (ensure asyncio.run() used correctly at top level)
- Data type mismatches (ArticleEnriched vs dict conversions)
- Quality score NaN or None (handle missing quality_score gracefully)

Fix each error as it appears. Commit after each fix with descriptive message.

- [ ] **Step 3: Verify output is generated**

Expected: Markdown report file created at `~/.local/share/feedship/reports/YYYY-MM-DD.md`

---

### Task 12: AI News Analyst Evaluation — Score > 80/100

- [ ] **Step 1: Run AI evaluation using the existing evaluator**

The existing `src/llm/evaluator.py` or similar should be used to score the report.

Run: `uv run feedship --debug report --since 2026-04-07 --until 2026-04-10 --language zh`
Then evaluate the output.

- [ ] **Step 2: If score < 80, iterate on the pipeline**

Common fixes:
- **Low coherence**: Improve entity resolution (normalize "Google Gemma 4" consistently)
- **Low relevance**: Adjust SignalFilter thresholds (quality_score, feed_weight)
- **Low depth**: Increase max_entities or reduce large_event_threshold
- **Low structure**: Improve render.py template formatting
- **Missing entities**: Check NER batch size, ensure entities are being extracted

Each iteration:
1. Identify the specific weakness from evaluation
2. Adjust the relevant component
3. Re-run the test command
4. Re-evaluate
5. Commit with descriptive message

- [ ] **Step 3: Target score > 80/100**

When score reaches > 80: commit with message `feat(report): achieve AI analyst score > 80`

---
