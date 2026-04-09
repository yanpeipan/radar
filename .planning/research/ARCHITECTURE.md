# LLM Architecture Research: Feedship LLM Feature Integration

**Domain:** Personal RSS reader with LLM-powered features
**Project:** Feedship Python CLI with LLM summarization, quality scoring, keyword extraction, topic clustering, and daily reports
**Researched:** 2026-04-07
**Confidence:** MEDIUM (based on existing codebase patterns; implementation details require provider selection)

## Executive Summary

LLM features integrate into Feedship through a dedicated `src/application/llm.py` module that provides four core functions: `summarize_article()`, `score_quality()`, `extract_keywords()`, and `generate_report()`. The existing architecture supports three trigger patterns: inline during high-weight feed fetches, on-demand via `summarize` CLI command, and scheduled via the existing OpenClaw integration for daily reports.

Storage extends SQLite with new article fields (summary, quality_score, keywords, tags, summarized_at) and ChromaDB with optional `article_summaries` and `article_keywords` collections. The template system uses Markdown files with Jinja2 placeholders stored in `~/.config/feedship/templates/`.

The build order follows natural dependencies: LLM client first, then storage extensions, then CLI commands, then trigger integration.

## Integration Architecture

### System Overview

```
src/
├── cli/
│   ├── summarize.py          # NEW: summarize command
│   ├── report.py            # NEW: daily report command
│   └── article.py           # MODIFIED: add --summarize flag to view
├── application/
│   ├── llm.py               # NEW: LLM client module
│   ├── article_view.py      # MODIFIED: call LLM on fetch
│   └── fetch.py             # MODIFIED: trigger LLM for high-weight feeds
├── storage/
│   ├── sqlite/
│   │   ├── impl.py          # MODIFIED: new article fields + queries
│   │   └── init.py          # MODIFIED: schema migration
│   └── vector.py            # MODIFIED: new collections
└── models.py                # MODIFIED: ArticleWithLLM dataclass

~/.config/feedship/
├── templates/               # NEW: report templates
│   ├── default.md
│   └── brief.md
└── config.yaml              # MODIFIED: LLM provider config
```

## 1. LLM Client Module (`src/application/llm.py`)

### Module Location

`src/application/llm.py` — follows existing convention where business logic lives in `application/`.

### Core Functions

```python
# src/application/llm.py

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

class LLMProvider(Protocol):
    """Protocol for LLM providers (openai, anthropic, ollama, etc.)."""
    def complete(self, prompt: str, **kwargs) -> str: ...
    def batch_complete(self, prompts: list[str], **kwargs) -> list[str]: ...

@dataclass
class LLMConfig:
    provider: str           # "openai", "anthropic", "ollama"
    model: str              # e.g., "gpt-4o-mini", "claude-3-haiku"
    api_key: str | None    # None for local ollama
    base_url: str | None   # For proxy/custom endpoints

@dataclass
class ArticleLLMData:
    article_id: str
    summary: str | None
    quality_score: float | None  # 0.0-1.0
    keywords: list[str] | None
    tags: list[str] | None
    summarized_at: str | None

def get_llm_provider() -> LLMProvider:
    """Get configured LLM provider from dynaconf settings."""
    ...

async def summarize_article(article_id: str, force: bool = False) -> ArticleLLMData:
    """Generate article summary using LLM.

    Returns cached result if already summarized unless force=True.
    """
    ...

async def score_quality(article_id: str, force: bool = False) -> float:
    """Score article quality 0.0-1.0 based on content depth, originality, clarity.

    Returns cached score if already scored unless force=True.
    """
    ...

async def extract_keywords(article_id: str, force: bool = False) -> list[str]:
    """Extract 5-10 keywords from article content.

    Returns cached keywords if already extracted unless force=True.
    """
    ...

async def batch_summarize(article_ids: list[str]) -> list[ArticleLLMData]:
    """Batch summarize multiple articles efficiently.

    Uses provider's batch/completion API when available.
    Falls back to sequential with concurrency limit.
    """
    ...

async def generate_report(
    article_ids: list[str],
    template: str = "default",
    **template_vars,
) -> str:
    """Generate daily digest report from articles using template.

    Template variables: date, article_count, feed_count, top_topics.
    """
    ...
```

### Provider Selection Rationale

| Provider | Pros | Cons | Best For |
|----------|------|------|----------|
| **openai** | Mature, cheap gpt-4o-mini | API key required, external | Cost-sensitive, reliable |
| **anthropic** | Claude 3.5 Haiku affordable | API key required | Quality-first |
| **ollama** | Free, local, private | Must run locally, slower | Privacy, offline |

**Recommendation:** Use `litellm` as abstraction layer — single interface for all providers, easy to switch. Add `litellm` to dependencies.

### Function Descriptions

**`summarize_article(article_id, force)`**
- Input: article_id from SQLite
- Output: 2-4 sentence summary in same language as article
- Cache: Check `summarized_at` field; skip if exists and not force
- LLM prompt: "Summarize this article in 2-4 sentences: {title}. {content[:2000]}"

**`score_quality(article_id, force)`**
- Input: article_id from SQLite
- Output: float 0.0-1.0
- Criteria: content depth (has substantive paragraphs), originality (not generic), clarity (well-structured)
- Cache: Check `quality_score` field; skip if exists and not force
- LLM prompt: "Rate this article's quality 0-100 for: depth (substantial paragraphs vs thin), originality (unique vs generic), clarity (well-structured vs rambling). Return only a number."

**`extract_keywords(article_id, force)`**
- Input: article_id from SQLite
- Output: list of 5-10 keywords
- Cache: Check `keywords` field; skip if exists and not force
- LLM prompt: "Extract 5-10 keywords from this article. Return as JSON array: [\"keyword1\", \"keyword2\", ...]"

**`generate_report(article_ids, template, **vars)`**
- Input: list of article_ids, template name, optional template variables
- Output: formatted Markdown report
- Template: Jinja2 template from `~/.config/feedship/templates/{template}.md`
- Context: Fetches articles from SQLite, passes to template

## 2. Storage Extension

### SQLite Schema Changes

**New columns in `articles` table:**

```sql
-- Added via ALTER TABLE in DatabaseInitializer
ALTER TABLE articles ADD COLUMN summary TEXT;
ALTER TABLE articles ADD COLUMN quality_score REAL;
ALTER TABLE articles ADD COLUMN keywords TEXT;  -- JSON array stored as string
ALTER TABLE articles ADD COLUMN tags TEXT;       -- JSON array stored as string
ALTER TABLE articles ADD COLUMN summarized_at TEXT;
```

**Migration in `src/storage/sqlite/init.py`:**

```python
_ARTICLES_LLM_COLUMNS = {
    "summary": "TEXT",
    "quality_score": "REAL",
    "keywords": "TEXT",  # JSON serialized list
    "tags": "TEXT",       # JSON serialized list
    "summarized_at": "TEXT",
}

# In DatabaseInitializer.init_db():
for col_name, col_type in _ARTICLES_LLM_COLUMNS.items():
    if col_name not in existing:
        cursor.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
```

**New storage functions in `src/storage/sqlite/impl.py`:**

```python
def get_article_with_llm(article_id: str) -> dict | None:
    """Get article with LLM fields populated."""
    ...

def update_article_llm(
    article_id: str,
    summary: str | None = None,
    quality_score: float | None = None,
    keywords: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Update LLM fields for an article."""
    now = datetime.now(timezone.utc).isoformat()
    # Build UPDATE query dynamically for non-None values
    ...

def list_articles_for_llm(
    limit: int = 50,
    since: str | None = None,
    unsummarized_only: bool = True,
) -> list[dict]:
    """List articles eligible for LLM processing."""
    ...
```

### ChromaDB Collection Changes

**Option A (Reuse existing `articles` collection):** Add LLM metadata to existing documents
- Pros: No new collections, simpler
- Cons: Metadata inflation, no separate keyword/summary search

**Option B (New collections for LLM embeddings):** Recommended
- `article_summaries` — embedding of summary text for semantic search on summaries
- `article_keywords` — embedding of keywords for topic clustering
- Reuse existing `articles` for full-content search

```python
# In src/storage/vector.py:

def get_summaries_collection():
    """Get or create article_summaries ChromaDB collection."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="article_summaries",
        metadata={"description": "Article summary embeddings for semantic search"},
    )

def get_keywords_collection():
    """Get or create article_keywords ChromaDB collection."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="article_keywords",
        metadata={"description": "Article keyword embeddings for topic clustering"},
    )

def add_summary_embedding(article_id: str, summary: str) -> None:
    """Add summary embedding for semantic similarity on summaries."""
    ...

def add_keyword_embedding(article_id: str, keywords: list[str]) -> None:
    """Add keyword embedding for topic clustering."""
    ...
```

## 3. Trigger Integration

### Three Trigger Patterns

| Trigger | When | Use Case |
|---------|------|----------|
| **Inline (fetch)** | During `feedship fetch` for high-weight feeds | Real-time enrichment |
| **On-demand** | User runs `feedship summarize` | Interactive exploration |
| **Scheduled** | OpenClaw cron fires daily | Daily digest generation |

### Pattern 1: Inline During Fetch

**Location:** `src/application/fetch.py` — modify `fetch_one_async()`

**Decision logic:**
```python
# After storing articles and adding embeddings in fetch_one_async()
if new_count > 0:
    for article_id, _ in article_id_map:
        feed = get_feed(article.feed_id)
        if feed.weight and feed.weight >= 0.7:  # High-weight threshold
            # Queue for LLM processing
            asyncio.create_task(summarize_article(article_id))
```

**Trade-offs:**
- Pro: High-value feeds always summarized
- Con: Adds latency to fetch cycle; rate limiting concerns

**Alternative:** Queue-based (batch after fetch completes):
```python
# At end of fetch_all_async() summary
high_weight_ids = [aid for aid, feed in zip(article_id_map, feeds)
                   if feed.weight >= 0.7]
if high_weight_ids:
    asyncio.create_task(batch_summarize(high_weight_ids))
```

### Pattern 2: On-Demand Summarize

**Location:** New CLI command `src/cli/summarize.py`

```python
@cli.command("summarize")
@click.argument("article-id", required=False)
@click.option("--all", "summarize_all", is_flag=True, help="Summarize all unsummarized")
@click.option("--feed-id", help="Summarize articles from specific feed")
@click.option("--force", is_flag=True, help="Re-summarize even if cached")
@click.option("--batch-size", default=10, help="Batch size for API calls")
def summarize(article_id, summarize_all, feed_id, force, batch_size):
    """Summarize articles using LLM."""
    ...
```

### Pattern 3: Scheduled Daily Report

**Location:** Existing OpenClaw integration + new `report` CLI command

```python
@cli.command("report")
@click.option("--date", default="today", help="Report date (YYYY-MM-DD)")
@click.option("--template", default="default", help="Template name")
@click.option("--output", type=click.Path(), help="Output file")
def report(date, template, output):
    """Generate daily digest report."""
    ...
```

**OpenClaw cron trigger (existing integration):**
```bash
openclaw cron add \
  --name "daily-ai-digest" \
  --cron "0 8 * * *" \
  --message "Generate daily AI digest. Run feedship report --date today --template default" \
  --deliver --channel whatsapp
```

## 4. CLI Commands

### New File: `src/cli/summarize.py`

```python
"""Article summarization commands."""
import asyncio
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.application.llm import summarize_article, batch_summarize
from src.storage.sqlite.impl import list_articles_for_llm

console = Console()

@cli.command("summarize")
@click.argument("article-id", required=False)
@click.option("--all", "summarize_all", is_flag=True)
@click.option("--feed-id")
@click.option("--force", is_flag=True)
@click.option("--batch-size", default=10)
@click.option("--json", "json_output", is_flag=True)
def summarize(article_id, summarize_all, feed_id, force, batch_size, json_output):
    """Summarize articles using LLM.

    Use ARTICLE_ID for single article, --all for batch.
    """
    if article_id and summarize_all:
        click.secho("Cannot use both ARTICLE_ID and --all", err=True, fg="red")
        sys.exit(1)

    if summarize_all:
        articles = list_articles_for_llm(limit=100, unsummarized_only=not force)
        article_ids = [a["id"] for a in articles]
        with Progress(SpinnerColumn(), TextColumn("Summarizing...")) as progress:
            task = progress.add_task("Summarizing articles", total=len(article_ids))
            # Batch processing with progress
            for i in range(0, len(article_ids), batch_size):
                batch = article_ids[i:i+batch_size]
                asyncio.run(batch_summarize(batch))
                progress.update(task, advance=len(batch))
    elif article_id:
        result = asyncio.run(summarize_article(article_id, force=force))
        if json_output:
            print_json(result)
        else:
            console.print(Panel(result.summary, title=result.article_id))
    else:
        click.secho("Provide ARTICLE_ID or use --all", err=True, fg="red")
        sys.exit(1)
```

### New File: `src/cli/report.py`

```python
"""Daily report generation command."""
import click
from datetime import datetime, timezone

from src.application.llm import generate_report
from src.storage.sqlite.impl import list_articles_for_llm

@cli.command("report")
@click.option("--date", default=None, help="Report date (YYYY-MM-DD)")
@click.option("--template", default="default", help="Template name in ~/.config/feedship/templates/")
@click.option("--output", type=click.Path(), help="Output file path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def report(date, template, output, json_output):
    """Generate daily digest report from recent articles.

    Uses template from ~/.config/feedship/templates/{template}.md
    """
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    articles = list_articles_for_llm(limit=200, since=date)
    article_ids = [a["id"] for a in articles]

    if not article_ids:
        click.secho(f"No articles found for {date}", fg="yellow")
        return

    report_content = asyncio.run(generate_report(
        article_ids=article_ids,
        template=template,
        date=date,
        article_count=len(article_ids),
    ))

    if output:
        Path(output).write_text(report_content)
        click.secho(f"Report saved to {output}", fg="green")
    else:
        console = Console()
        console.print(report_content)
```

### Modified File: `src/cli/__init__.py`

Add new commands to CLI group:
```python
from src.cli.summarize import summarize
from src.cli.report import report

cli.add_command(summarize)
cli.add_command(report)
```

## 5. Template System

### Template Directory

`~/.config/feedship/templates/` (platformdirs user_config_dir)

### Template Format

Jinja2 Markdown with predefined variables:

```jinja2
# AI 日报 — {{ date }}

**主编导读 (Editor's Note)：**
{{ editor_note }}

## A. AI五层蛋糕

{% for layer, items in ai_stack.items() %}
### {{ layer }}
{% for item in items %}
{{ loop.index }}. {{ item.topic }}
   [{{ item.count }}]篇来源：{% for src in item.sources %}[**{{ src.title }}**]({{ src.url }}){% if not loop.last %}, {% endif %}{% endfor %}
{% endfor %}
{% endfor %}

## B. 精选推荐

{% for topic, articles in featured.items() %}
### {{ topic }}
{% for article in articles %}
{{ loop.index }}. [**{{ article.title }}**]({{ article.url }})
   来源: {{ article.feed_name }} | 权重: {{ article.weight }}
   推荐理由: {{ article.reason }}
{% endfor %}
{% endfor %}

## C. 创业信号

### 核心杠杆
{% for item in core_leverage %}
{{ loop.index }}. [{{ item.name }}]({{ item.url }})：{{ item.summary }}
   **降维打击点**：{{ item.differentiator }}
{% endfor %}
```

### Built-in Template Variables

| Variable | Type | Description |
|----------|------|-------------|
| `date` | str | Report date (YYYY-MM-DD) |
| `article_count` | int | Total articles in report |
| `feed_count` | int | Unique feeds in report |
| `articles` | list[dict] | Full article data with LLM fields |
| `top_topics` | list[str] | Most common keywords |
| `editor_note` | str | Auto-generated 2-sentence overview |

### Template Loading

```python
import platformdirs
from jinja2 import Environment, FileSystemLoader, select_autoescape

def get_template_env() -> Environment:
    template_dir = Path(platformdirs.user_config_dir("feedship")) / "templates"
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(),
    )

def render_template(template_name: str, **vars) -> str:
    env = get_template_env()
    template = env.get_template(f"{template_name}.md")
    return template.render(**vars)
```

## 6. Configuration Extension

### New config.yaml fields

```yaml
# LLM Configuration
llm:
  provider: "openai"                    # openai | anthropic | ollama | litellm
  model: "gpt-4o-mini"                   # Model name
  api_key: ${OPENAI_API_KEY}            # Env var reference
  base_url: null                        # For proxy/custom endpoints
  temperature: 0.3                      # Lower = more consistent
  max_tokens: 500                       # For summaries

# LLM Processing thresholds
llm_processing:
  auto_summarize_weight_threshold: 0.7  # Feed weight to auto-summarize
  batch_size: 10                        # Articles per batch API call
  rate_limit_rpm: 60                    # Provider rate limit

# Template settings
templates:
  default: "default"
  dir: "~/.config/feedship/templates"
```

## Build Order (Dependency Graph)

```
Phase 1: LLM Client Module
├── Add litellm to dependencies
├── Create src/application/llm.py
│   ├── LLMConfig dataclass
│   ├── LLMProvider protocol
│   ├── get_llm_provider() from dynaconf
│   ├── summarize_article() — basic implementation
│   └── _build_prompt() helper
└── Unit tests for llm.py

Phase 2: Storage Extension
├── Database migration in init.py (new columns)
├── New storage functions in impl.py:
│   ├── update_article_llm()
│   ├── get_article_with_llm()
│   └── list_articles_for_llm()
├── ChromaDB collections in vector.py:
│   ├── get_summaries_collection()
│   └── get_keywords_collection()
└── Unit tests for storage

Phase 3: CLI Commands
├── Create src/cli/summarize.py
│   ├── summarize command (single + batch)
│   └── progress reporting
├── Create src/cli/report.py
│   └── report command with template rendering
├── Modify src/cli/__init__.py to register commands
└── Integration tests

Phase 4: Trigger Integration
├── Modify src/application/fetch.py:
│   └── Add LLM queue for high-weight feeds (optional)
├── Create template files in ~/.config/feedship/templates/
│   ├── default.md (based on REPORT_FORMAT.md)
│   └── brief.md
├── Modify config.yaml with LLM settings
└── User documentation: docs/llm-features.md

Phase 5: Advanced Features
├── Topic clustering using keyword embeddings
├── Quality-based feed filtering
├── Personalized ranking using LLM scores
└── Export to Obsidian/Notion
```

### Dependency Rationale

1. **LLM client first** — All other components depend on it
2. **Storage second** — CLI and fetch depend on data schema
3. **CLI third** — Depends on storage + LLM client working
4. **Trigger fourth** — Depends on all pieces working; templates are data
5. **Advanced fifth** — Depends on everything else; nice-to-have

## Integration Points Summary

### New vs Modified Files

| File | Action | Reason |
|------|--------|--------|
| `src/application/llm.py` | NEW | Core LLM functionality |
| `src/storage/sqlite/init.py` | MODIFY | Add new columns via ALTER |
| `src/storage/sqlite/impl.py` | MODIFY | Add LLM field queries |
| `src/storage/vector.py` | MODIFY | Add new collections |
| `src/cli/summarize.py` | NEW | Summarize command |
| `src/cli/report.py` | NEW | Report command |
| `src/cli/__init__.py` | MODIFY | Register new commands |
| `src/application/fetch.py` | MODIFY | Optional: auto-summarize high-weight |
| `src/application/article_view.py` | MODIFY | Optional: LLM enrichment on view |
| `src/models.py` | MODIFY | Add ArticleWithLLM if needed |
| `config.yaml` | MODIFY | Add LLM config section |
| `~/.config/feedship/templates/` | NEW | Template directory |

### Key Integration Points

1. **Dynaconf config** — All LLM settings via `settings.llm.*`
2. **Storage context manager** — Existing pattern `with get_db() as conn:`
3. **Async boundaries** — Use `asyncio.to_thread()` for LLM calls
4. **Error handling** — LLM failures non-critical; log and continue
5. **Caching** — Every LLM function checks `summarized_at` before calling provider

## Anti-Patterns to Avoid

### Anti-Pattern 1: LLM Calls in Hot Path

**What:** Calling LLM synchronously during article fetch.

**Why bad:** Adds 1-5 seconds per high-weight article; fetch becomes unusable.

**Instead:** Queue LLM work for after fetch completes via `asyncio.create_task()`.

### Anti-Pattern 2: No Cache Invalidation

**What:** Always re-summarize on every call without checking existing data.

**Why bad:** Wastes API calls, costs money, slow.

**Instead:** Check `summarized_at` field; skip if exists and `force=False`.

### Anti-Pattern 3: Large Batch Without Backpressure

**What:** Sending 100 articles to LLM API at once.

**Why bad:** Provider rate limits, potential timeout, no progress visibility.

**Instead:** Process in batches of 10 with progress bar and rate limiting.

### Anti-Pattern 4: Storing Raw LLM Output Without Validation

**What:** Saving LLM response directly to DB without parsing.

**Why bad:** LLM output varies; may include extra text, invalid JSON.

**Instead:** Parse/validate output, store structured data; log raw for debugging.

## Scalability Considerations

| Scale | Articles | LLM Strategy |
|-------|----------|--------------|
| 110 feeds, 50-200/feed | ~11K-22K total | Summarize top 20% by weight = ~2.5K summaries |
| Daily new | ~500-1000 | Summarize high-weight daily = ~100-200/day |
| Cost (gpt-4o-mini @ $0.15/1M tokens) | ~2.5K summaries | ~$5-10/month |

**Rate limiting:** Set `llm_processing.rate_limit_rpm` to 60 for OpenAI tier-1.

**Caching:** ChromaDB embeddings cached locally; summaries in SQLite.

**Memory:** LLM processing is sequential CPU-bound; use `asyncio.to_thread()`.

## Data Flow Diagrams

### Summarize On-Demand

```
feedship summarize ARTICLE_ID
    │
    ▼
src/cli/summarize.py:summarize()
    │
    ▼
src/storage.sqlite.impl:get_article_with_llm()
    │ (fetch article content)
    ▼
src/application/llm:summarize_article()
    │ check summarized_at → skip if exists
    ▼
LLM Provider API (openai/anthropic/ollama)
    │
    ▼
src/storage.sqlite.impl:update_article_llm()
    │ (save summary, quality_score, keywords)
    ▼
Output to console / JSON
```

### Daily Report Generation

```
openclaw cron fires at 8 AM
    │
    ▼
feedship report --date today
    │
    ▼
src/storage.sqlite.impl:list_articles_for_llm(since=DATE)
    │ (fetch articles with LLM data)
    ▼
Load template: ~/.config/feedship/templates/default.md
    │
    ▼
src/application/llm:generate_report()
    │ for each section, gather data + call LLM if needed
    ▼
Render Jinja2 template with data
    │
    ▼
Output Markdown report
    │
    ▼
openclaw deliver --channel whatsapp
```

---

*Research for: LLM feature integration with Feedship architecture*
*Confidence: MEDIUM — Provider selection depends on user preference; template format based on existing ai-daily skill*
