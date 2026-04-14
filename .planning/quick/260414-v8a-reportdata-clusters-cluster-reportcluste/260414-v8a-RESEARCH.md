# Quick Task 260414-v8a: ReportData.clusters to cluster: ReportCluster - Research

**Researched:** 2026-04-14
**Domain:** Report pipeline data model refactor
**Confidence:** HIGH

## Summary

The task is to replace `ReportData.clusters: dict[str, list[ReportCluster]]` with a single `cluster: ReportCluster` field. This eliminates tag-based dict lookup in favor of a tree structure where `ReportData.cluster` is the root and section-level clusters live in `cluster.children`.

**Impact scope:** 3 Python files, 1 template, 1 test file.

## Current Structure

### ReportData.clusters (dict)
```python
# models.py:106
clusters: dict[str, list[ReportCluster]] = field(default_factory=dict)
```

- Key = topic name (e.g., "AI应用", "AI模型"), Value = list of ReportCluster
- Built by `ReportData.build(heading_tree)` which matches heading titles to cluster names
- `add_article(cluster_name, item)` adds to `self.clusters[cluster_name]`

### Template access pattern
```jinja2
# ai_daily_report.md.j2:7
{%- for cluster in report_data.clusters.get("AI应用", []) %}
```
- Hardcoded section names (AI应用, AI模型, AI基础设施, AI芯片, AI能源)
- Each section does a dict lookup

## Changes Required

### 1. models.py — ReportData

| Before | After | Impact |
|--------|-------|--------|
| `clusters: dict[str, list[ReportCluster]]` | `cluster: ReportCluster` | Core type change |
| `total_articles` iterates `.clusters.values()` | Must traverse `cluster.children` recursively | Logic rewrite |
| `add_article(cluster_name, item)` uses dict key | Must find/create child cluster by name in `cluster.children` | Logic rewrite |
| `build(heading_tree)` builds `dict[str, list]` | Must build `ReportCluster` tree with children | Logic rewrite |
| `get_cluster(name)` searches dict | Must search cluster tree recursively | Simpler but different |
| `ReportData(clusters={}, ...)` constructor | `ReportData(cluster=ReportCluster(...), ...)` | Caller update |

**New root cluster initialization:**
```python
# Root cluster replaces the dict — holds section clusters as children
cluster: ReportCluster = field(default_factory=ReportCluster)
```

**New total_articles logic (conceptual):**
```python
@property
def total_articles(self) -> int:
    def count(c: ReportCluster) -> int:
        return len(c.articles) + sum(count(child) for child in c.children)
    return count(self.cluster)
```

**New build() logic (conceptual):**
- HeadingNode.children become `ReportCluster.children` at each level
- No dict — tree structure directly

### 2. insight.py — InsightChain

| Before | After |
|--------|-------|
| `_collect_all_clusters(clusters: dict[str, list[ReportCluster]])` | `_collect_all_clusters(cluster: ReportCluster)` |
| `input.clusters` (dict) | `input.cluster` (single cluster) |
| Iterates `clusters.values()` then flattens | Recursively traverses `cluster.children` |

**New collection logic:**
```python
def _collect_all_clusters(self, cluster: ReportCluster) -> list[ReportCluster]:
    all_clusters = [cluster]
    for child in cluster.children:
        all_clusters.extend(self._collect_all_clusters(child))
    return all_clusters
```

### 3. models.py — BuildReportDataChain

```python
# Before
report_data = ReportData(clusters={}, date_range={}, target_lang=..., heading_tree=...)
report_data.add_articles(items, ...)
report_data.build(heading_tree)

# After — cluster is the root, initialized differently
report_data = ReportData(cluster=ReportCluster(title="root"), date_range={}, ...)
report_data.add_articles(items, ...)  # adds to cluster.children by tag name
report_data.build(heading_tree)  # builds children tree
```

### 4. ai_daily_report.md.j2 — Template rewrite required

**Current pattern (dict lookup by hardcoded section name):**
```jinja2
## AI应用
{%- for cluster in report_data.clusters.get("AI应用", []) %}
```

**After change (iterate cluster.children):**
```jinja2
{%- for section in report_data.cluster.children %}
## {{ section.title }}
{%- if section.children %}
  {%- for child in section.children %}
> {{ child.summary or '' }}
    {%- for article in child.articles %}
- [{{ article.translation }}]({{ article.link }})
    {%- endfor %}
  {%- endfor %}
{%- else %}
> {{ section.summary or '' }}
  {%- for article in section.articles %}
- [{{ article.translation }}]({{ article.link }})
  {%- endfor %}
{%- endif %}
{% else %}
（本期暂无相关来源）
{% endfor %}
```

The template currently has 5 hardcoded sections. With the tree structure, the number and names of sections come from `report_data.cluster.children` (populated by `heading_tree` from the template's own heading structure). The sections are no longer hardcoded in the template — they are driven by the heading tree.

### 5. test_report.py

- `ReportData(clusters={}, ...)` → `ReportData(cluster=ReportCluster(...), ...)` (lines 401-404)
- `isinstance(data.clusters, dict)` → `isinstance(data.cluster, ReportCluster)` (line 459)

## Impact Summary

| File | Lines | Change Type |
|------|-------|-------------|
| `src/application/report/models.py` | ~60 | Logic rewrite: `clusters` dict to `cluster` tree, `total_articles`, `add_article`, `build`, `get_cluster` |
| `src/application/report/insight.py` | ~10 | `input.clusters` → `input.cluster`, `_collect_all_clusters` signature and body |
| `src/application/report/generator.py` | ~5 | `ReportData(clusters={})` → `ReportData(cluster=ReportCluster(...))` |
| `templates/ai_daily_report.md.j2` | ~100 | Replace 5 hardcoded dict lookups with `cluster.children` iteration |
| `tests/test_report.py` | ~5 | Constructor and isinstance check |

## What Does NOT Change

- **CLI (`report.py`):** Uses `data.total_articles` and `data.date_range` — no direct `clusters` access. The `ReportTemplate.render(data)` call passes the whole `ReportData` object unchanged.
- **`ReportCluster` model:** `title`, `content`, `summary`, `tags`, `children`, `articles` — unchanged.
- **`ReportArticle` model:** unchanged.
- **`template.py`:** `render()` just passes `report_data` to Jinja2 — no internal `clusters` access.

## Runtime State Inventory

Not applicable — this is a code refactor only. No databases, services, or OS-level registrations are affected.

## Validation Architecture

| Req ID | Behavior | Test Type | File |
|--------|----------|-----------|------|
| REQ-1 | `ReportData.cluster` is a `ReportCluster` instance | unit | `tests/test_report.py` |
| REQ-2 | `total_articles` counts all articles in cluster tree | unit | `tests/test_report.py` |
| REQ-3 | `build(heading_tree)` populates `cluster.children` | unit | `tests/test_report.py` |
| REQ-4 | Template renders without KeyError on dict lookup | smoke | Manual `feedship report` |

## Open Questions

1. **Root cluster title:** What should `ReportCluster(title=?)` be for the root? Currently the dict has no name — the keys are section names. Possible options: `title=""` (empty), `title="root"`, or `title=heading_tree.title` if it has one.
2. **Section-less articles:** If an article's tag does not match any section in `heading_tree`, where does it go? Currently `add_article` creates a cluster at the top level. With the tree structure, these would need a place (e.g., `cluster.children` with a special section name like "Other").

## Sources

- `src/application/report/models.py` — ReportData, ReportCluster, BuildReportDataChain
- `src/application/report/insight.py` — InsightChain._collect_all_clusters
- `src/application/report/generator.py` — _entity_report_async
- `src/application/report/template.py` — ReportTemplate.render
- `templates/ai_daily_report.md.j2` — Template access pattern
- `tests/test_report.py` — Test assertions for clusters
- `src/cli/report.py` — CLI usage (no clusters access)
