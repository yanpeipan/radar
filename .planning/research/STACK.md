# Stack Research: LLM Stack for Feedship v1.11

**Domain:** Python CLI tool LLM integration for article summarization, quality scoring, and report generation
**Researched:** 2026-04-07
**Confidence:** MEDIUM-HIGH (verified PyPI versions, community patterns)

## Executive Summary

The v1.11 milestone requires adding LLM capabilities for article summarization, quality scoring, keyword extraction, and template-based daily report generation. This research recommends **LiteLLM 1.83.x** as the primary LLM client (unified interface for OpenAI/Azure/Ollama), with the existing **ChromaDB 1.5.x** already supporting vector storage for summaries and keywords. The existing trafilatura integration provides full-text content extraction. No Pydantic changes needed; configuration extends via the existing YAML-based config.

## Recommended Stack

### LLM Client (Primary Addition)

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| **litellm** | 1.83.x | Unified LLM interface (OpenAI, Azure, Ollama, Anthropic, 100+ providers) | Single API for all LLM providers; drop-in OpenAI compatibility; built-in cost tracking; retries, timeouts, streaming |
| **openai** | 2.30.x | OpenAI SDK (required by LiteLLM; also direct use for Assistants API) | LiteLLM uses this under the hood; direct use for advanced OpenAI features |
| **anthropic** | 0.89.x | Anthropic SDK for Claude models | Direct SDK for Claude when not going through LiteLLM |

### Vector Storage (Already Present)

| Library | Version | Status | Notes |
|---------|---------|--------|-------|
| **chromadb** | 1.5.x | Already in `ml` extras | Existing `articles` collection for embeddings; create new collections for summaries and keywords |
| **sentence-transformers** | 3.0.x | Already in `ml` extras | Reuse for embedding summaries/keywords if needed |

### Content Extraction (Already Present)

| Library | Version | Status | Notes |
|---------|---------|--------|-------|
| **trafilatura** | 1.0.x+ | Already a dependency | Existing `fetch_url_content()` in `article_view.py` provides markdown content |
| **scrapling** | 0.4.x | Already a dependency | HTTP fetching (used by trafilatura internally) |

### Configuration (Already Present)

| Library | Status | Notes |
|---------|--------|-------|
| **Pydantic** (`pydantic`, `pydantic-settings`) | Already in use | `FeedshipSettings` in `src/application/config.py` loads from `config.yaml` |
| **PyYAML** | Already a dependency | `config.yaml` uses `${VAR}` syntax for env var interpolation |

### NOT Adding (Avoid)

| Library | Why Not | Use Instead |
|---------|---------|-------------|
| **LangChain** | Overkill for simple summarization/scoring; adds 15+ dependencies; complex abstractions | Direct LiteLLM calls |
| **LlamaIndex** | Data framework, not a simple LLM client; heavy dependency | LiteLLM + direct ChromaDB queries |
| **Instructor** | Task-specific; adds another abstraction layer | LiteLLM with structured output via `response_format` |
| **Guidance** | Template-based prompting library; niche use case | Jinja2 templates + LiteLLM |
| **textblob** | Old NLP library; no LLM support | LiteLLM for keyword extraction |
| **spacy** | Heavy NLP pipeline; overkill | LiteLLM for entity/keyword extraction |

---

## LiteLLM Deep Dive

### Why LiteLLM over Direct SDKs

**1. Provider Flexibility**
```python
# OpenAI
import litellm
response = litellm.completion("gpt-4o-mini", messages=[...])

# Ollama (local)
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
response = litellm.completion("ollama/llama3", messages=[...])

# Azure OpenAI
os.environ["AZURE_API_KEY"] = "..."
response = litellm.completion("azure/gpt-4o-mini", messages=[...])
```

**2. Unified Interface**
- Same `litellm.completion()` API regardless of provider
- Easy to switch between OpenAI (development) and Ollama (production/local)
- Built-in streaming, retries, timeouts

**3. Structured Outputs**
```python
from litellm import completion
import json

response = completion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Extract keywords from: ..."}],
    response_format={"type": "json_object", "schema": {"keywords": ["string"]}}
)
```

**4. Cost Tracking**
```python
response = completion(model="gpt-4o-mini", messages=[...])
print(response._hidden_params["response_cost"])  # Token cost tracking
```

### LiteLLM Configuration

**config.yaml additions needed:**
```yaml
llm:
  provider: "openai"  # openai | ollama | azure | anthropic
  model: "gpt-4o-mini"  # gpt-4o-mini | gpt-4o | ollama/llama3 | azure/gpt-4o-mini
  api_key: ${OPENAI_API_KEY}  # or ${ANTHROPIC_API_KEY} for Claude
  base_url: ${OLLAMA_BASE_URL}  # http://localhost:11434 for Ollama
  max_tokens: 500
  temperature: 0.3  # Lower for consistent summaries
  timeout: 60  # seconds
```

---

## Ollama Integration (Local Models)

### Recommended Models for Feedship

| Model | Size | Use Case | Why |
|-------|------|----------|-----|
| **llama3.2** | 2GB | General summarization | Good quality, reasonable speed |
| **llama3.2:latest** | 2GB | Latest improvements | |
| **mistral-nemo** | 7GB | Better at following instructions | Higher quality output |
| **qwen2.5** | 3GB | Multilingual (Chinese support) | Good for mixed-language feeds |

### Ollama Setup

```bash
# Install Ollama
brew install ollama  # macOS
# or: curl -fsSL https://ollama.com/install.sh | sh

# Pull models
ollama pull llama3.2
ollama pull mistral-nemo

# Run Ollama server (if not using default)
ollama serve
```

### Ollama vs OpenAI Tradeoffs

| Aspect | Ollama (Local) | OpenAI (Cloud) |
|--------|-----------------|----------------|
| Cost | Free (compute only) | Per-token pricing |
| Privacy | 100% local | Data leaves machine |
| Speed | 10-50 tok/s (GPU), 1-5 tok/s (CPU) | ~100 tok/s |
| Quality | Good for summarization | State-of-the-art |
| Availability | Requires local setup | Always available |
| Offline | Works offline | Requires internet |

**Recommendation:** Support both. Use OpenAI for development and cloud users; Ollama for privacy-conscious users and self-hosters. LiteLLM makes this trivial.

---

## ChromaDB Extensions for LLM Features

### Existing Collection: `articles`
- Stores article embeddings (384-dim from `all-MiniLM-L6-v2`)
- Used for semantic search

### New Collections for LLM Features

```python
# Summary vectors - for finding similar summaries
collection_summaries = client.get_or_create_collection(
    name="article_summaries",
    metadata={"description": "Summary embeddings for article clustering"}
)

# Keyword/keyword vectors - for topic grouping
collection_keywords = client.get_or_create_collection(
    name="article_keywords",
    metadata={"description": "Keyword embeddings for topic clustering"}
)
```

### Schema for Summary Collection

```python
{
    "article_id": "nanoid123",      # Link to SQLite article
    "summary": "Markdown summary",   # LLM-generated summary (stored as document)
    "keywords": ["AI", "LLM"],      # Extracted keywords
    "quality_score": 0.85,          # LLM quality score
    "topics": ["technology", "AI"], # Topic tags
    "generated_at": "2026-04-07T10:00:00Z",
    "model": "gpt-4o-mini"          # Which model generated this
}
```

---

## Configuration Design

### Extend Existing Pydantic Settings

```python
# src/application/config.py additions

class FeedshipSettings(BaseSettings):
    # ... existing fields ...

    # LLM configuration
    llm: dict = Field(default_factory=dict)

    @field_validator("llm", mode="before")
    @classmethod
    def validate_llm_config(cls, v: dict) -> dict:
        defaults = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "max_tokens": 500,
            "temperature": 0.3,
            "timeout": 60,
        }
        if isinstance(v, dict):
            return {**defaults, **v}
        return defaults
```

### Environment Variables

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For Ollama (local)
export OLLAMA_BASE_URL="http://localhost:11434"

# For Azure OpenAI
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://your-resource.openai.azure.com/"
export AZURE_API_VERSION="2024-02-01"

# For Anthropic (Claude)
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Integration with Existing Codebase

### Article View Integration

```python
# src/application/article_view.py already has:
# - fetch_url_content() -> returns {"url", "title", "content", "extracted_at"}
# - Uses trafilatura for extraction

# New LLM module would use:
from src.application.llm import summarize_article, score_quality, extract_keywords

def process_article_with_llm(article_id: str):
    article = get_article_detail(article_id)
    content = article.get("content") or fetch_url_content(article["link"])["content"]

    summary = summarize_article(content)
    keywords = extract_keywords(content)
    quality = score_quality(content)

    store_llm_results(article_id, summary, keywords, quality)
```

### Async Considerations

```python
# LiteLLM is synchronous; wrap in asyncio.to_thread() for non-blocking
async def summarize_async(content: str) -> str:
    return await asyncio.to_thread(summarize_article, content)

# Or use LiteLLM's async wrapper
import litellm
response = await litellm.acompletion(model="gpt-4o-mini", messages=[...])
```

---

## What to Add to pyproject.toml

```toml
[project]
dependencies = [
    # ... existing dependencies ...
]

[project.optional-dependencies]
ml = [
    # ... existing ml deps ...
    "litellm>=1.83.0,<2",  # LLM client (adds openai, anthropic as deps)
]
# Or add as required (not optional) if LLM is core to v1.11
```

**Recommended:** Add `litellm` as a **required dependency** (not optional) since v1.11's core features (summarization, quality scoring, reports) all require LLM access.

---

## Report Generation Architecture

### Template-Based Reports

```python
# src/application/report.py
from datetime import datetime
from typing import Protocol

class ReportTemplate(Protocol):
    def render(self, data: dict) -> str: ...

class DailyDigestTemplate:
    """Daily digest with sections: top articles, topics, quality summary."""

    def render(self, data: dict) -> str:
        return f"""# Daily Digest - {data['date']}

## Top Articles ({data['article_count']})

{data['top_articles_markdown']}

## Topics Covered

{', '.join(data['topics'])}

## Quality Overview

Average quality score: {data['avg_quality']:.2f}
High-quality articles: {data['high_quality_count']}
"""
```

### LLM-Enhanced Report

```python
async def generate_daily_report(articles: list[dict], template: ReportTemplate) -> str:
    # 1. Fetch content for articles without full text
    # 2. Generate summaries in parallel
    summaries = await asyncio.gather(*[
        summarize_async(a["content"]) for a in articles
    ])

    # 3. Extract keywords and cluster topics
    topics = await cluster_topics(summaries)

    # 4. Score article quality
    quality_scores = await asyncio.gather(*[
        score_quality_async(a["content"]) for a in articles
    ])

    # 5. Render template
    report_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "article_count": len(articles),
        "top_articles_markdown": format_articles(articles, summaries, quality_scores),
        "topics": topics,
        "avg_quality": sum(quality_scores) / len(quality_scores),
        "high_quality_count": sum(1 for q in quality_scores if q > 0.8),
    }

    return template.render(report_data)
```

---

## Dependencies Summary

### Required for v1.11

| Package | Version | Purpose |
|---------|---------|---------|
| **litellm** | 1.83.x | Unified LLM client |
| **openai** | 2.30.x | OpenAI SDK (LiteLLM dependency) |
| **anthropic** | 0.89.x | Anthropic SDK (LiteLLM can use, or direct for Claude) |

### Already Present (No Change)

| Package | Status |
|---------|--------|
| chromadb | Already in ml extras |
| sentence-transformers | Already in ml extras |
| trafilatura | Already a dependency |
| scrapling | Already a dependency |
| pydantic, pydantic-settings | Already used |
| pyyaml | Already a dependency |

### NOT Adding

- LangChain, LlamaIndex, Instructor, Guidance, textblob, spacy

---

## Installation Commands

```bash
# Core LLM dependencies
uv add litellm

# For OpenAI
uv add openai

# For Claude (direct SDK)
uv add anthropic

# Or via extras
uv add "feedship[ml]"  # includes litellm
```

---

## Confidence Assessment

| Component | Confidence | Notes |
|-----------|------------|-------|
| LiteLLM recommendation | HIGH | Verified current version (1.83.4), widely used (20k+ stars), active development |
| OpenAI SDK | HIGH | Official SDK, verified current version (2.30.0) |
| Anthropic SDK | HIGH | Official SDK for Claude, verified version (0.89.0) |
| Ollama integration | MEDIUM | Uses standard HTTP API; LiteLLM provides abstraction |
| ChromaDB extensions | HIGH | Existing pattern well-understood; new collections are straightforward |
| Config approach | HIGH | Extends existing Pydantic+YAML pattern |

---

## Sources

- [LiteLLM GitHub](https://github.com/BerriAI/litellm) - Unified LLM interface
- [LiteLLM Documentation](https://docs.litellm.ai/) - Provider support, structured outputs
- [OpenAI Python SDK](https://github.com/openai/openai-python) - Official SDK
- [Ollama Python Client](https://github.com/ollama/ollama-python) - Local model support
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-python) - Claude support
- [ChromaDB Documentation](https://docs.trychroma.com/) - Multi-collection usage
- [PyPI: litellm](https://pypi.org/project/litellm/) - Version 1.83.4
- [PyPI: openai](https://pypi.org/project/openai/) - Version 2.30.0
- [PyPI: anthropic](https://pypi.org/project/anthropic/) - Version 0.89.0

---

*Stack research for: Feedship v1.11 LLM 智能报告*
*Researched: 2026-04-07*
