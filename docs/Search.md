# Search

## 目标架构（路线 A）

三种查询方法返回原始信号，统一在应用层通过 `combine_scores` 合并，最后可选 Cross-Encoder 重排。

---

## 实现状态：v2.0 已完成 ✅

所有目标功能已在 v2.0 milestone 中实现并发布。

### ArticleListItem（已完成）

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
    score: float = 1.0       # 兼容字段（已废弃）
```

### 三种查询方法（已完成）

| 方法 | 所在层 | score 含义 | 状态 |
|---|---|---|---|
| `vector.search_articles_semantic` | storage.vector | 原始 `cos_sim` | ✅ 已修复，返回 raw vec_sim |
| `storage_impl.search_articles` (FTS5) | storage.sqlite | Sigmoid `1 / (1 + exp(bm25 * factor))` | ✅ 已修复 |
| `storage_impl.list_articles` | storage.sqlite | freshness 填充 | ✅ 已实现 |

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

### 搜索类型与权重配置

调用点根据搜索类型显式传入不同权重：

| 搜索类型 | alpha | beta | gamma | delta | 说明 |
|---|---|---|---|---|---|
| 语义搜索 `--semantic` | 0.3 | 0.3 | 0.2 | **0.0** | 无 BM25 信号 |
| 关键词搜索（默认） | 0.3 | 0.3 | 0.0 | 0.2 | 无 vec_sim 信号 |
| 混合搜索（可选） | 0.3 | 0.3 | 0.1 | 0.1 | 两种信号都启用 |

> **注意**：`delta=0` 时 `delta × bm25_score = 0`，语义搜索只使用 `gamma × vec_sim` 作为文本相关信号。

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
# 全局缓存（函数外部）
_model = None
_tokenizer = None

def _load_reranker():
    """Lazy load Cross-Encoder model and tokenizer."""
    global _model, _tokenizer
    if _model is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        model_name = "BAAI/bge-reranker-base"
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _model.eval()
    return _model, _tokenizer

async def rerank(query: str, candidates: list[ArticleListItem], top_k: int = 20) -> list[ArticleListItem]:
    """Cross-Encoder rerank using BAAI/bge-reranker-base (lazy loaded)."""
    if not candidates:
        return candidates

    try:
        model, tokenizer = _load_reranker()
    except ImportError as e:
        raise RuntimeError(
            "Cross-Encoder rerank requires torch and transformers. "
            "Install with: pip install torch transformers"
        ) from e

    # Build query-document pairs
    texts = [(query, c.title or "") for c in candidates]
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt", max_length=512)

    with torch.no_grad():
        scores = model(**inputs).logits.squeeze(-1).numpy()

    # Fill ce_score and sort
    for i, c in enumerate(candidates):
        c.ce_score = float(scores[i])

    candidates.sort(key=lambda x: x.ce_score, reverse=True)
    return candidates[:top_k]
```

> **关键点**：`torch` 和 `transformers` 的导入放在 `_load_reranker()` 函数内部，而非模块顶部；全局缓存 `_model`/`_tokenizer` 避免重复加载。

### 6. 新增 `application/combine.py`

```python
def combine_scores(candidates: list[ArticleListItem], alpha=0.3, beta=0.3, gamma=0.2, delta=0.2) -> list[ArticleListItem]:
    """统一合并多信号分数，返回按 final_score 降序的列表"""
```

### 7. CLI `article search` 命令调整

- `--semantic` 时：`vector_search` → 可选 `rerank` → `combine_scores(gamma=0.2, delta=0.0)`
- 默认 FTS5 时：`search_articles` → 可选 `rerank` → `combine_scores(gamma=0.0, delta=0.2)`
- `alpha/beta` 始终传入；`gamma/delta` 根据搜索类型显式传入
- CLI 不直接暴露 `gamma/delta`，由搜索类型决定（保持接口简洁）

---

## 已解决问题

- ✅ BM25 归一化：Sigmoid + factor 可配置（默认 0.5）
- ✅ Cross-Encoder 调用时机：rerank 在 combine_scores 之前，ce_score=0 时 alpha×0=0
- ✅ delta 参数：显式传入 delta=0（语义搜索）或 delta=0.2（关键词搜索）
- ✅ 参数配置：gamma/delta 由搜索类型决定
- ✅ lazy import：Cross-Encoder torch/transformers 在 rerank() 函数内部加载，全局缓存 _model/_tokenizer
