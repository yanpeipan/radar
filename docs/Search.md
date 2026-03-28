# Search

## 目标架构（路线 A）

三种查询方法返回原始信号，统一在应用层通过 `combine_scores` 合并，最后可选 Cross-Encoder 重排。

---

## 当前状态

### ArticleListItem（现状）

```python
@dataclass
class ArticleListItem:
    id: str
    feed_id: str
    feed_name: str
    title: Optional[str]
    link: Optional[str]
    guid: str
    pub_date: Optional[int]  # Unix timestamp INTEGER
    description: Optional[str]
    score: float = 1.0  # 目前未统一使用
```

### 三种查询方法（现状）

| 方法 | 所在层 | score 含义 | 问题 |
|---|---|---|---|
| `vector.search_articles_semantic` | storage.vector | 硬编码 `0.5×cos + 0.2×fresh + 0.3×weight` | 已是组合分，无法被 combine_scores 重新组合 |
| `storage_impl.search_articles` (FTS5) | storage.sqlite | `1 / (1 + abs(bm25_score))` | BM25 负分用 abs() 反转语义有误 |
| `storage_impl.list_articles` | storage.sqlite | 无 score，固定 1.0 | score 字段未被使用 |

---

## 目标结构

### ArticleListItem（目标）

```python
@dataclass
class ArticleListItem:
    id: str
    feed_id: str
    feed_name: str
    title: Optional[str]
    link: Optional[str]
    guid: str
    pub_date: Optional[int]  # Unix timestamp INTEGER
    description: Optional[str]
    # 原始信号分数（由各查询方法填充）
    vec_sim: float = 0.0      # ChromaDB cosine similarity (0-1)
    bm25_score: float = 0.0   # FTS5 BM25 normalized score (0-1)
    freshness: float = 0.0    # 时间衰减分数 (0-1, 牛顿冷却定律)
    source_weight: float = 0.3 # 来源权重 (feed.weight)
    ce_score: float = 0.0      # Cross-Encoder score (0-1, rerank 后填充)
    final_score: float = 0.0  # combine_scores 最终分数
```

> **说明**：`score` 字段保留兼容，但最终由 `final_score` 统一排序。

---

## 三种查询方法（目标）

### 1. ChromaDB 向量检索 → `vector.search_articles_semantic`

- **返回**：原始 `vec_sim`（cosine similarity, 0-1）
- **不包含**：freshness、source_weight 组合（这些由 combine_scores 统一处理）
- **参数**：`query_text`, `limit`, `since`, `until`, `on`
- **实现改动**：移除硬编码加权，score 直接返回 `cos_sim`

### 2. FTS5 全文搜索 → `storage_impl.search_articles`

- **返回**：原始 `bm25_score`（归一化到 0-1）
- **BM25 归一化**：Sigmoid 变换，在 Python 层计算

  ```python
  def sigmoid_norm(bm25_raw: float, factor: float = 0.5) -> float:
      """将负值 BM25 映射到 (0,1) 区间，值越大越相关"""
      return 1 / (1 + math.exp(bm25_raw * factor))
  ```

  - SQLite BM25 返回负值（越负 = 越相关）
  - `factor` 为可配置参数，默认 `0.5`，通过 `config.py` 管理
  - 在 Python 层计算（`search_articles` 获取原始 BM25 后立即归一化）
  - 候选集 ≤ 200，`math.exp()` 开销可忽略（< 0.01s）
  - 若担心极值下溢可加保护：`exp_arg = max(bm25_raw * factor, -50)`
- **参数**：`query`, `limit`, `feed_id`, `since`, `until`, `on`
- **配置项**：`bm25_factor`（默认 0.5）

### 3. 列表查询 → `storage_impl.list_articles`

- **返回**：原始 `freshness`（时间衰减分数 0-1）
- **score 字段**：填充 `freshness` 而非固定 1.0
- **参数**：`limit`, `feed_id`, `since`, `until`, `on`
- **注意**：列表查询无 vec_sim / bm25_score / ce_score，设为 0.0

---

## Cross-Encoder 重排（可选）

- **模型**：`BAAI/bge-reranker-base`
- **输入**：query + document pairs
- **输出**：`ce_score`（0-1 概率）
- **调用时机**：在 `combine_scores` 之前，对候选列表重排
- **跳过条件**：`list_articles` 无 query，跳过 Cross-Encoder
- **top_k**：rerank 后取 top 结果送入 combine_scores

---

## 统一合并函数（应用层）

### `combine_scores(candidates, alpha=0.3, beta=0.3, gamma=0.2, delta=0.2)`

```python
def combine_scores(
    candidates: list[ArticleListItem],
    alpha: float = 0.3,  # Cross-Encoder score 权重（有 ce_score 时生效）
    beta: float = 0.3,   # 新鲜度权重
    gamma: float = 0.2,   # 向量相似度权重（vec_sim）
    delta: float = 0.2,   # BM25 权重（bm25_score）
) -> list[ArticleListItem]:
    """
    牛顿冷却定律 freshness = exp(-days_ago / half_life_days)
    half_life_days 默认 7 天
    """
    half_life_days = 7
    now = datetime.now(timezone.utc)

    for c in candidates:
        # 时间衰减
        if c.pub_date:
            pub_dt = datetime.fromtimestamp(c.pub_date, tz=timezone.utc)
            days_ago = (now - pub_dt).days
            c.freshness = math.exp(-days_ago / half_life_days)
        else:
            c.freshness = 0.0

        # 最终分数
        ce = c.ce_score if c.ce_score > 0 else 0.0  # ce_score=0 表示未 rerank
        c.final_score = (
            alpha * ce +
            beta * c.freshness +
            gamma * c.vec_sim +
            delta * c.bm25_score
        )

    candidates.sort(key=lambda x: x.final_score, reverse=True)
    return candidates
```

### 参数含义

| 参数 | 默认值 | 含义 |
|---|---|---|
| `alpha` | 0.3 | Cross-Encoder relevance score 权重 |
| `beta` | 0.3 | 新鲜度（时间衰减）权重 |
| `gamma` | 0.2 | 向量相似度（ChromaDB cos_sim）权重 |
| `delta` | 0.2 | BM25 关键词权重 |

> **注意**：当 `ce_score = 0`（未做 rerank）时，`alpha * 0 = 0`，相当于纯信号组合。

---

## 完整流程

```
用户查询 "AI 最新进展"

┌─ vector_search (ChromaDB)
│   → vec_sim = cosine_similarity
│   → candidates (with vec_sim)
│
├─ search_articles (FTS5 BM25)
│   → bm25_score (normalized 0-1)
│   → candidates (with bm25_score)
│
└─ list_articles (fallback / 无 query)
    → freshness score
    → candidates (with freshness)

      ↓ 合并所有 candidates（去重，UNION）
      ↓ Cross-Encoder rerank（可选，top_k candidates）
      ↓ combine_scores(alpha, beta, gamma, delta)
      ↓ sort by final_score

最终结果 list[ArticleListItem]（按 final_score 降序）
```

---

## 实现改动清单

### 1. `ArticleListItem` 扩展字段

新增：`vec_sim`, `bm25_score`, `freshness`, `source_weight`, `ce_score`, `final_score`

### 2. `storage/vector.py` — `search_articles_semantic`

- 移除硬编码 `0.5 * cos + 0.2 * fresh + 0.3 * weight` 组合
- score 直接返回 `cos_sim`（vec_sim）
- 确保 `pub_date` 以 INTEGER unix timestamp 传给 ChromaDB metadata filter

### 3. `storage/sqlite/impl.py` — `search_articles`

- 修复 BM25 归一化：改用 Sigmoid 变换 `sigmoid_norm(bm25_raw, factor)`，factor 从 `config.py` 读取（默认 0.5）
- 获取原始 BM25 负分后立即在 Python 层归一化，填充 `ArticleListItem.bm25_score`

### 4. `storage/sqlite/impl.py` — `list_articles`

- 增加 `freshness` 分数填充
- 查询结果按 `pub_date DESC` 本身已是时间排序，freshness 字段作为信号备用

### 5. 新增 `application/rerank.py`

```python
async def rerank(query: str, candidates: list[ArticleListItem], top_k: int = 20) -> list[ArticleListItem]:
    """Cross-Encoder rerank using BAAI/bge-reranker-base"""
    # model.encodeCrossEncoder(query, documents) → ce_scores
    # 填充 ce_score 到 ArticleListItem
    # 返回 top_k
```

### 6. 新增 `application/combine.py`

```python
def combine_scores(candidates: list[ArticleListItem], alpha=0.3, beta=0.3, gamma=0.2, delta=0.2) -> list[ArticleListItem]:
    """统一合并多信号分数，返回按 final_score 降序的列表"""
```

### 7. CLI `article search` 命令调整

- `--semantic` 时：vector_search → 可选 rerank → combine_scores
- 默认 FTS5 时：search_articles → 可选 rerank → combine_scores
- 参数透传 `alpha/beta/gamma/delta` 或使用合理默认值

---

## 待讨论问题

1. **BM25 归一化细节**：min/max score 在查询时如何估算（滑动窗口还是固定参数）？
2. **Cross-Encoder 调用时机**：rerank 放在 combine_scores 之前，但 combine_scores 里的 `alpha * ce` 如何处理 ce_score=0 的情况？（已用 fallback = 0）
3. **delta 参数**：当只用语义搜索（无 FTS5）时，delta 是否设为 0？
4. **参数配置**：alpha/beta/gamma/delta 是否通过 CLI 参数暴露，还是写死默认值？
5. **向量化模型**：`BAAI/bge-reranker-base` 依赖 torch，是否通过 lazy import 避免非必要加载？
