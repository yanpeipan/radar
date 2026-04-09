# Feature Research: Feedship v1.11 LLM Features

**Domain:** LLM-powered article summarization, quality scoring, keyword extraction, topic clustering, and daily report generation
**Researched:** 2026-04-07
**Confidence:** MEDIUM (established patterns from training data; web search unavailable for verification)

## Executive Summary

This document details the five core LLM features for Feedship v1.11:
1. **Summarization** (single-article + multi-article aggregated)
2. **Quality scoring** (0-1 score)
3. **Keyword extraction** (3-5 keywords per article)
4. **Topic clustering** (grouping articles by theme)
5. **Daily reports** (template-based Markdown output)

These features have clear dependencies: summarization and keyword extraction are independent but both feed into topic clustering. Quality scoring is independent. Daily reports consume all other features' outputs. The "AI Five-Layer Cake" template (Application/Model/Infrastructure/Chip/Energy) provides a content taxonomy that aligns well with topic clustering.

---

## 1. Summarization

### Feature Description

**Single-Article Summarization**
- Input: Full article content (markdown from trafilatura)
- Output: 3-5 sentence summary (100-150 tokens)
- Purpose: Quick read comprehension, search result previews

**Multi-Article Aggregated Summary**
- Input: Multiple articles grouped by topic/cluster
- Output: 2-3 paragraph synthesis per topic group
- Purpose: Daily report section content

### Implementation Patterns

#### Single-Article Summary (3-5 sentences)

```python
# Prompt pattern for single-article summary
SINGLE_SUMMARY_PROMPT = """You are a professional content summarizer.
Given the following article content, write a concise summary of 3-5 sentences.

Requirements:
- Capture the main point and key takeaways
- Use clear, professional language
- Do not start with "This article..."
- Be informative without being verbose

Article Title: {title}
Article Content:
{content}

Summary:"""

def summarize_article(content: str, title: str, llm_client) -> str:
    response = llm_client.completion(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": SINGLE_SUMMARY_PROMPT.format(title=title, content=content)
        }],
        max_tokens=150,
        temperature=0.3  # Low for consistency
    )
    return response["choices"][0]["message"]["content"]
```

#### Multi-Article Aggregated Summary (per topic)

```python
# Prompt pattern for multi-article synthesis
AGGREGATE_SUMMARY_PROMPT = """You are a tech news analyst. Given a collection of articles on the same topic, write a synthesized summary.

Requirements:
- Identify the common theme across all articles
- Highlight key points (with specific facts/numbers when available)
- Note any conflicting viewpoints or different angles
- Write 2-3 paragraphs
- Do not list articles; integrate information naturally

Articles:
{articles}

Synthesized Summary:"""

def summarize_topic_cluster(articles: list[dict], llm_client) -> str:
    # Format articles for prompt
    articles_text = "\n\n".join([
        f"## {a['title']}\n{a['summary'] or a.get('content', '')[:500]}"
        for a in articles
    ])

    response = llm_client.completion(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": AGGREGATE_SUMMARY_PROMPT.format(articles=articles_text)
        }],
        max_tokens=400,
        temperature=0.4
    )
    return response["choices"][0]["message"]["content"]
```

### Complexity Assessment

| Aspect | Complexity | Notes |
|--------|------------|-------|
| Single-article summary | LOW | Simple prompt, single LLM call |
| Multi-article aggregate | MEDIUM | Requires grouping first, longer context |
| Streaming large volumes | MEDIUM | Need async/batch processing for 100+ feeds |
| Summary caching | LOW | Store in SQLite, invalidate on --force |

### Dependencies

- **Input:** Full article content (trafilatura markdown)
- **Output stored:** SQLite `article_summaries` table
- **Used by:** Topic clustering (as input), daily reports (as content)

---

## 2. Quality Scoring

### Feature Description

- **Output:** Float score 0.0 to 1.0
- **Purpose:** Rank articles by quality, filter low-quality content
- **Factors:** Content richness, source authority, novelty

### Scoring Algorithm

```python
# Multi-factor quality scoring
QUALITY_SCORING_PROMPT = """You are an article quality analyst. Rate the quality of this article from 0.0 to 1.0.

Evaluation Criteria:
1. **Content Richness** (0-0.4): Depth of information, presence of facts/data, analysis vs surface-level
2. **Source Authority** (0-0.3): Credible sources cited, expert quotes, official data
3. **Writing Quality** (0-0.15): Clarity, structure, no filler
4. **Uniqueness** (0-0.15): Original insight, not generic coverage

Article Title: {title}
Article Content (first 1000 chars):
{content[:1000]}

Respond with ONLY a JSON object:
{{"score": 0.00, "breakdown": {{"content_richness": 0.0, "source_authority": 0.0, "writing_quality": 0.0, "uniqueness": 0.0}}, "reasoning": "brief note"}}"""

def score_article_quality(content: str, title: str, feed_weight: float, llm_client) -> dict:
    response = llm_client.completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": QUALITY_SCORING_PROMPT.format(title=title, content=content)}],
        response_format={"type": "json_object"},
        max_tokens=200,
        temperature=0.1
    )

    result = json.loads(response["choices"][0]["message"]["content"])

    # Combine LLM quality score with feed weight
    final_score = result["score"] * 0.7 + feed_weight * 0.3

    return {
        "score": round(final_score, 2),
        "breakdown": result["breakdown"],
        "raw_llm_score": result["score"],
        "feed_weight_factor": feed_weight
    }
```

### Feed Weight Integration

```sql
-- SQLite schema for quality scores
CREATE TABLE article_quality (
    article_id TEXT PRIMARY KEY,
    score REAL NOT NULL,           -- 0.0 to 1.0
    content_richness REAL,
    source_authority REAL,
    writing_quality REAL,
    uniqueness REAL,
    feed_weight_used REAL,
    model TEXT,
    generated_at TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

-- Feed weight comes from existing feeds table
-- SELECT weight FROM feeds WHERE id = ?;
```

### Complexity Assessment

| Aspect | Complexity | Notes |
|--------|------------|-------|
| Single score generation | LOW | Single LLM call with JSON output |
| Score storage | LOW | SQLite insert/update |
| Score-based filtering | LOW | SQL WHERE clause |
| Score-based ranking | LOW | ORDER BY score DESC |
| Consistency across batches | MEDIUM | Temperature 0.1, clear criteria |

### Dependencies

- **Input:** Article content, feed weight (from feeds table)
- **Output:** SQLite `article_quality` table
- **Used by:** Daily report (sorting/filtering), search ranking

---

## 3. Keyword Extraction

### Feature Description

- **Output:** 3-5 keywords/tags per article
- **Storage:** SQLite + ChromaDB embeddings
- **Purpose:** Tagging, semantic search, topic clustering

### Implementation Pattern

```python
# Keyword extraction prompt
KEYWORD_EXTRACTION_PROMPT = """Extract 3-5 keywords or short phrases (2-4 words each) from this article.

Requirements:
- Focus on: technologies, companies, products, concepts, trends
- Use proper nouns when applicable
- Return as JSON array of strings
- Do not duplicate or overly overlap

Article Title: {title}
Article Content:
{content[:2000]}

Keywords:"""

def extract_keywords(content: str, title: str, llm_client) -> list[str]:
    response = llm_client.completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": KEYWORD_EXTRACTION_PROMPT.format(title=title, content=content)}],
        response_format={"type": "json_object"},
        max_tokens=100,
        temperature=0.2
    )

    result = json.loads(response["choices"][0]["message"]["content"])
    return result.get("keywords", [])
```

### Storage Schema

```sql
-- SQLite storage for keywords
CREATE TABLE article_keywords (
    article_id TEXT PRIMARY KEY,
    keywords TEXT NOT NULL,  -- JSON array
    model TEXT,
    generated_at TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

-- ChromaDB storage for semantic search
-- Collection: article_keywords
-- Document: keyword text (for semantic matching)
-- Metadata: article_id, keywords array
```

### ChromaDB Integration

```python
# Add keywords to ChromaDB for semantic search
def index_keywords(article_id: str, keywords: list[str], chroma_client):
    collection = chroma_client.get_or_create_collection("article_keywords")

    # Each keyword becomes an embedding entry
    for keyword in keywords:
        collection.add(
            documents=[keyword],
            metadatas=[{"article_id": article_id, "keyword": keyword}],
            ids=[f"{article_id}_{keyword}"]
        )

# Semantic keyword search
def search_by_keyword(query: str, top_k: int = 5) -> list[dict]:
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    return results
```

### Complexity Assessment

| Aspect | Complexity | Notes |
|--------|------------|-------|
| Keyword extraction | LOW | Simple LLM call, JSON output |
| SQLite storage | LOW | Insert/update |
| ChromaDB indexing | LOW | Embedding generation + insert |
| Semantic search | LOW | Query existing collection |

### Dependencies

- **Input:** Article content
- **Output:** SQLite `article_keywords`, ChromaDB `article_keywords`
- **Used by:** Topic clustering (as input), daily reports (as tags)

---

## 4. Topic Clustering

### Feature Description

- **Purpose:** Group articles by theme for daily report organization
- **Algorithm options:**
  1. **Embedding similarity** (pure ML, fast)
  2. **LLM-based classification** (accurate, explainable)
  3. **Hybrid** (embedding for rough grouping + LLM for refinement)

### Algorithm Options

#### Option A: Embedding Similarity (Fast, Scalable)

```python
from sentence_transformers import SentenceTransformer

def cluster_by_embeddings(articles: list[dict], threshold: float = 0.7) -> list[list[dict]]:
    """
    Cluster articles based on embedding cosine similarity.
    Returns list of clusters, each cluster is a list of articles.
    """
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Generate embeddings for article summaries
    texts = [a.get('summary', a.get('content', '')[:500]) for a in articles]
    embeddings = model.encode(texts)

    # Compute similarity matrix
    from sklearn.metrics.pairwise import cosine_similarity
    similarity_matrix = cosine_similarity(embeddings)

    # Greedy clustering: connect articles above threshold
    clusters = []
    assigned = set()

    for i, article in enumerate(articles):
        if i in assigned:
            continue

        cluster = [article]
        assigned.add(i)

        for j in range(i + 1, len(articles)):
            if j not in assigned and similarity_matrix[i][j] >= threshold:
                cluster.append(articles[j])
                assigned.add(j)

        clusters.append(cluster)

    return clusters
```

#### Option B: LLM Classification (Accurate, Template-Driven)

```python
# Define topic categories
TOPIC_CATEGORIES = {
    "AI_Application": ["AI applications in industry", "AI product launches", "AI case studies"],
    "AI_Model": ["model releases", "model training", "model benchmarks", "foundation models"],
    "AI_Infrastructure": ["cloud AI", "AI platforms", "MLOps", "training infrastructure"],
    "AI_Chip": ["AI accelerators", "GPUs", "custom silicon", "semiconductor"],
    "AI_Energy": ["AI power consumption", "green AI", "data center energy", "efficiency"],
    "Startup_Signals": ["funding", "acquisitions", "IPO", "founder news"],
    "Content_Topics": ["general tech news", "other topics not fitting above"]
}

CLASSIFICATION_PROMPT = """Classify this article into ONE of these categories:

1. AI_Application - AI applications in industry, product launches, case studies
2. AI_Model - Model releases, training, benchmarks, foundation models
3. AI_Infrastructure - Cloud AI, platforms, MLOps, training infrastructure
4. AI_Chip - AI accelerators, GPUs, custom silicon, semiconductors
5. AI_Energy - AI power consumption, green AI, data center efficiency
6. Startup_Signals - Funding, acquisitions, IPO, founder news
7. Content_Topics - General tech news or topics not fitting above

Article Title: {title}
Article Summary: {summary}

Respond with ONLY JSON:
{{"category": "CategoryName", "confidence": 0.00, "reasoning": "brief"}}"""

def classify_article(article: dict, llm_client) -> dict:
    response = llm_client.completion(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": CLASSIFICATION_PROMPT.format(
                title=article['title'],
                summary=article.get('summary', '')[:300]
            )
        }],
        response_format={"type": "json_object"},
        max_tokens=150,
        temperature=0.1
    )

    return json.loads(response["choices"][0]["message"]["content"])
```

#### Option C: Hybrid (Recommended)

```python
def cluster_articles_hybrid(articles: list[dict], llm_client) -> dict[str, list[dict]]:
    """
    Hybrid approach:
    1. Use embedding similarity for initial grouping (fast)
    2. Use LLM to identify the dominant topic per cluster (accurate)
    3. Merge small clusters into larger ones if needed
    """
    # Step 1: Embedding-based clustering
    initial_clusters = cluster_by_embeddings(articles, threshold=0.65)

    # Step 2: LLM topic identification per cluster
    final_clusters = {}

    for cluster in initial_clusters:
        if len(cluster) == 1:
            # Single article: classify directly
            topic = classify_article(cluster[0], llm_client)["category"]
        else:
            # Multiple articles: synthesize topic
            topic = synthesize_cluster_topic(cluster, llm_client)

        if topic not in final_clusters:
            final_clusters[topic] = []
        final_clusters[topic].extend(cluster)

    return final_clusters

def synthesize_cluster_topic(cluster: list[dict], llm_client) -> str:
    summary = summarize_topic_cluster(cluster, llm_client)[:200]

    response = llm_client.completion(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"What is the dominant topic of this article cluster? Choose from: {list(TOPIC_CATEGORIES.keys())}\n\nCluster summary: {summary}"
        }],
        max_tokens=50,
        temperature=0.1
    )

    return response["choices"][0]["message"]["content"].strip()
```

### Complexity Assessment

| Aspect | Complexity | Notes |
|--------|------------|-------|
| Embedding clustering | LOW | Sentence-transformers + sklearn |
| LLM classification | MEDIUM | Per-cluster LLM call |
| Hybrid approach | MEDIUM | Combination of both |
| Handling outliers | LOW | Single-article clusters OK |

### Dependencies

- **Input:** Article summaries (from summarization), article content
- **Output:** Cluster mapping (article_id -> topic)
- **Used by:** Daily report (section organization)

---

## 5. Daily Report

### Feature Description

- **CLI:** `feedship report --template xxx --since --until`
- **Output:** Markdown file with configurable sections
- **Content:** Aggregated from all other LLM features

### Template Structure

The "AI Five-Layer Cake" provides a content taxonomy:

```markdown
# Daily Report: {date}

## AI Five-Layer Cake

### Application Layer
Articles about AI applications in industry, product launches, use cases.

{aggregated_summary_for_Application}

Articles:
- [Article 1](url) - {summary} (quality: 0.85)
- [Article 2](url) - {summary} (quality: 0.78)

### Model Layer
Articles about AI models, releases, training, benchmarks.

{aggregated_summary_for_Model}

Articles:
- ...

### Infrastructure Layer
Articles about cloud AI, platforms, MLOps, training infrastructure.

### Chip Layer
Articles about AI accelerators, GPUs, custom silicon.

### Energy Layer
Articles about AI power consumption, green AI, data center efficiency.

## Startup Signals
Articles about funding, acquisitions, IPO, founder news.

## Content Topics
Other tech news not fitting above categories.

---

*Report generated by Feedship v1.11 | {article_count} articles | Date range: {since} to {until}*
```

### Template Processing

```python
from jinja2 import Template
from datetime import datetime

REPORT_TEMPLATE = """# Daily Report: {{ date }}

## AI Five-Layer Cake

{% for layer in ai_layers %}
### {{ layer.name }}
{{ layer.summary }}

{% for article in layer.articles %}
- [{{ article.title }}]({{ article.link }}) - {{ article.summary }} (quality: {{ article.quality }})
{% endfor %}

{% endfor %}

## Startup Signals

{% for article in startup_articles %}
- [{{ article.title }}]({{ article.link }}) - {{ article.summary }} (quality: {{ article.quality }})
{% endfor %}

## Content Topics

{% for article in other_articles %}
- [{{ article.title }}]({{ article.link }}) - {{ article.summary }} (quality: {{ article.quality }})
{% endfor %}

---

*Report generated by Feedship v1.11 | {{ article_count }} articles | Date range: {{ since }} to {{ until }}*
"""

def generate_daily_report(
    articles: list[dict],
    clusters: dict[str, list[dict]],
    template: str = REPORT_TEMPLATE
) -> str:
    from jinja2 import Template

    t = Template(template)

    return t.render(
        date=datetime.now().strftime("%Y-%m-%d"),
        ai_layers=[{
            "name": "Application Layer",
            "summary": clusters.get("AI_Application", [{"summary": ""}])[0].get("summary", ""),
            "articles": clusters.get("AI_Application", [])
        }, {
            "name": "Model Layer",
            "summary": clusters.get("AI_Model", [{"summary": ""}])[0].get("summary", ""),
            "articles": clusters.get("AI_Model", [])
        }, {
            "name": "Infrastructure Layer",
            "summary": clusters.get("AI_Infrastructure", [{"summary": ""}])[0].get("summary", ""),
            "articles": clusters.get("AI_Infrastructure", [])
        }, {
            "name": "Chip Layer",
            "summary": clusters.get("AI_Chip", [{"summary": ""}])[0].get("summary", ""),
            "articles": clusters.get("AI_Chip", [])
        }, {
            "name": "Energy Layer",
            "summary": clusters.get("AI_Energy", [{"summary": ""}])[0].get("summary", ""),
            "articles": clusters.get("AI_Energy", [])
        }],
        startup_articles=clusters.get("Startup_Signals", []),
        other_articles=clusters.get("Content_Topics", []),
        article_count=len(articles),
        since="2026-04-06",
        until="2026-04-07"
    )
```

### CLI Interface

```python
# CLI command structure
@click.command()
@click.option("--template", default="default", help="Template name or path")
@click.option("--since", type=click.DateTime(), help="Start date (YYYY-MM-DD)")
@click.option("--until", type=click.DateTime(), help="End date (YYYY-MM-DD)")
@click.option("--min-quality", type=float, default=0.0, help="Minimum quality score filter")
@click.option("--groups", multiple=True, help="Filter by feed group")
@click.option("--output", "-o", type=click.Path(), help="Output file (default: stdout)")
@click.option("--force", is_flag=True, help="Regenerate even if cached")
def report(template, since, until, min_quality, groups, output, force):
    """Generate daily digest report."""
    # 1. Fetch articles for date range
    # 2. Filter by min_quality, groups
    # 3. Run LLM features (summarize, score, extract keywords, cluster)
    # 4. Render template
    # 5. Output
```

### Complexity Assessment

| Aspect | Complexity | Notes |
|--------|------------|-------|
| Date range filtering | LOW | SQL WHERE clause |
| Template rendering | LOW | Jinja2 |
| Aggregating all features | MEDIUM | Need all prior features working |
| Large reports (100+ articles) | MEDIUM | Batch LLM calls, progress indicator |

### Dependencies

```
Daily Report
    │
    ├── Summarization ─────────────> Article summaries
    ├── Quality Scoring ───────────> Quality scores (filtering/ranking)
    ├── Keyword Extraction ─────────> Keywords (optional display)
    └── Topic Clustering ──────────> Organized sections
```

---

## Feature Dependency Graph

```
                    ┌─────────────────┐
                    │  Article List   │
                    │  (from SQLite)  │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
    │Summarization│  │Quality Score│  │Keyword Extract  │
    │  (summary)  │  │   (score)    │  │   (keywords)    │
    └──────┬──────┘  └──────┬──────┘  └────────┬────────┘
           │                 │                 │
           └────────┬────────┴─────────────────┘
                    │           │
                    ▼           ▼
            ┌─────────────────────────┐
            │    Topic Clustering     │
            │    (AI Five-Layer +     │
            │     Startup Signals +   │
            │     Content Topics)      │
            └───────────┬─────────────┘
                        │
                        ▼
            ┌─────────────────────────┐
            │     Daily Report        │
            │   (Jinja2 template)     │
            └─────────────────────────┘
```

---

## MVP Priority Order

### Phase 1: Core Pipeline
1. **Summarization** (single-article) - Foundation for everything
2. **Quality scoring** - Used for filtering and ranking
3. **SQLite storage** - Persist results

### Phase 2: Organization
4. **Keyword extraction** - Tags and semantic search
5. **Topic clustering** - Group articles by category

### Phase 3: Output
6. **Daily report generation** - Template-based output
7. **CLI integration** - `feedship summarize`, `feedship report`

---

## Complexity Summary

| Feature | Implementation | LLM Calls | Storage | Notes |
|---------|--------------|-----------|---------|-------|
| Single-article summary | LOW | 1 per article | SQLite | Cacheable |
| Multi-article aggregate | MEDIUM | 1 per cluster | SQLite | Depends on clustering |
| Quality scoring | LOW | 1 per article | SQLite | Fast JSON output |
| Keyword extraction | LOW | 1 per article | SQLite + ChromaDB | Embed keywords |
| Topic clustering | MEDIUM | 1 per cluster | Memory/SQLite | Hybrid approach |
| Daily report | LOW-MEDIUM | N per cluster | File output | Consumes all above |

---

## Sources

- [LiteLLM Documentation](https://docs.litellm.ai/) - LLM client patterns
- [Sentence-Transformers](https://www.sbert.net/) - Embedding-based clustering
- [Jinja2 Documentation](https://jinja.palletsprojects.com/) - Template rendering
- Established summarization prompting patterns from training data

---

*Feature research for: Feedship v1.11 LLM 智能报告生成*
*Researched: 2026-04-07*
