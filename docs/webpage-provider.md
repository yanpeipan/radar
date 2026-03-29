# WebpageProvider 设计文档

## 1. 背景与目标

### 1.1 问题

Radar 当前通过 `RSSProvider` 订阅 RSS/Atom Feed，对于没有 RSS 的**JS 渲染新闻站点**（机器之心、36kr 等）无能为力。

用户希望：
> 提供任意新闻站点 URL（如 `https://www.jiqizhixin.com/`），`feed add` 后系统自动抓取文章列表、最近开源项目等信息。

### 1.2 目标

- 实现 `WebpageProvider` — 一个通用的 JS 渲染网页抓取 Provider
- 使用 **Scrapling DynamicFetcher**（Playwright 后端）渲染页面
- 通过**站点配置**（CSS Selector）提取文章列表项
- **Readability 兜底**：无配置的站点也能提取内容
- 复用现有 Provider 架构（match / priority / crawl / parse / feed_meta）

---

## 2. 技术方案

### 2.1 核心依赖

```
scrapling[playwright]  # JS 渲染 + CSS 选择器解析
playwright             # 浏览器自动化
readability-lxml       # 通用文章提取兜底（已存在）
```

Scrapling 的 `DynamicFetcher` = Playwright 包装器，API 简洁，支持 `wait_selector`、`page_action`。

### 2.2 Provider 接口实现

```python
class WebpageProvider:
    def match(self, url: str) -> bool:
        # 匹配所有 HTTP URL，排除 GitHub
        return url.startswith("http") and "github.com" not in url.lower()

    def priority(self) -> int:
        return 100  # 高于 RSS(50)，低于 GitHub(200)

    def crawl(self, url: str) -> List[Raw]:
        # Step 1: 尝试站点专用配置提取
        #   → 有 SITE_CONFIG + 提取到 items → 返回
        # Step 2: Readability 兜底
        #   → 将 URL 本身作为文章页面提取

    def parse(self, raw: Raw) -> Article:
        # dict → Article dataclass

    def feed_meta(self, url: str) -> Feed:
        # 抓取页面提取 <title>，返回 Feed 对象
```

### 2.3 站点配置格式

```python
SITE_CONFIGS: dict[str, dict] = {
    "jiqizhixin.com": {
        "_default": {           # 首页 https://www.jiqizhixin.com/
            "wait_selector": ".home__article-item",
            "item": ".home__article-item",
            "title": ".home__article-item__title",
            "time": ".home__article-item__time",
            "tags": ".home__article-item__tag-item",
            "description": None,
            "link": None,       # HTML 无 href，通过 UUID 构造
        },
        "articles": {           # 文档库 https://www.jiqizhixin.com/articles
            "wait_selector": ".article-card",
            "item": ".article-card",
            "title": ".article-card__title",
            "time": ".article-card__time",
            "tags": ".article-card__tags > div",
            "description": None,
            "link": None,
        },
    },
    "36kr.com": {
        "_default": {
            "wait_selector": ".article-item",
            "item": ".article-item",
            "title": ".title",
            "time": ".time",
            "tags": ".tag",
            "description": ".desc",
            "link": "a[href]",
        },
    },
}
```

**配置查找逻辑**：
1. 提取 URL 路径第一个 segment（如 `/articles` → `"articles"`）
2. 在 `site_config` 中查找路径名匹配的配置
3. 未找到则使用 `"_default"`

### 2.4 无 href 链接的解决方案

**问题**：机器之心文章链接由 JS 动态生成，HTML 中 `.home__article-item` 内无 `<a>` 标签。

**发现**：文章列表的 `<img>` src 包含文章 UUID：
```
https://image.jiqizhixin.com/uploads/article/cover_image/{uuid}/xxx.jpg
```

**解决**：
```python
def _construct_article_link(item, root) -> str | None:
    imgs = item.css('img')
    for img in imgs:
        src = img.attrib.get('src', '')
        uuid = re.search(r'/article/cover_image/([0-9a-f-]{36})/', src)
        if uuid:
            return f"https://www.jiqizhixin.com/article/{uuid.group(1)}"
    return None
```

### 2.5 日期解析

支持多种中文日期格式：
- `03月27日` → `2026-03-27`（自动推断年份）
- `2024-12-01` → `2024-12-01`
- `3分钟前` → 当天

---

## 3. 抓取流程

```
feed add https://www.jiqizhixin.com/
  │
  ├─ discover_or_default(url)
  │    → WebpageProvider (priority=100, match=True)
  │
  ├─ provider.feed_meta(url)
  │    → DynamicFetcher 抓页面
  │    → 提取 <title> → "机器之心"
  │    → 返回 Feed(name="机器之心", url=...)
  │
  └─ feed fetch
       │
       ├─ 有 SITE_CONFIG？
       │  └─ Yes: _crawl_impl() → CSS Selector 提取 12 条
       │
       └─ No / 提取为空？
          └─ _crawl_readability() → 提取单篇文章
```

---

## 4. Readability 兜底

当站点无 SITE_CONFIGS 配置时，`_crawl_readability()` 接管：

```python
def _crawl_readability(self, url: str) -> List[Raw]:
    # 1. DynamicFetcher 渲染页面（JS-aware）
    r = fetcher.fetch(url, timeout=30000)

    # 2. Readability 解析
    doc = Document(body, url=url)

    # 3. 提取字段
    return [{
        "title": doc.short_title(),
        "link": url,                    # URL 本身即文章链接
        "pub_date": today,
        "tags": [],
        "description": text_content[:500],  # 正文纯文本前500字
        "content": doc.summary(),             # 完整文章 HTML
    }]
```

**适用场景**：
- 用户直接 `feed add` 一个具体的文章页面
- 新闻站点列表页无 SITE_CONFIG 时，降级为单文章提取

---

## 5. 文件结构

```
src/providers/
├── __init__.py              # Provider 注册表（含 load_providers）
├── base.py                  # ContentProvider 协议
├── rss_provider.py          # RSS/Atom Provider
├── github_release_provider.py
├── default_provider.py      # 兜底 Provider
└── webpage_provider.py      # ★ 新增：JS 渲染网页 Provider
```

---

## 6. 扩展新站点清单

| 站点 | 关键选择器 | 备注 |
|------|-----------|------|
| jiqizhixin.com | `.home__article-item` | 首页 + `/articles` 两套配置 ✅ |
| 36kr.com | `.article-item .title` | 待配置 |
| thepaper.cn | 待探索 | |

扩展方式：在 `SITE_CONFIGS` 字典中添加站点域名 → 选择器配置即可。

---

## 7. 开源项目版块（待探索）

用户提到机器之心有"开源项目"页面。需确认：
- 是单独 URL 路径（如 `/opensource`）？
- 还是文章列表内带特定标签的项目？
- 还是有专门的子域名/子页面？

---

## 8. 分页支持（待实现）

"加载更多"类分页场景，可通过 `page_action` 执行点击/滚动操作，提取多页数据。

---

## 9. 依赖安装

```bash
pip install scrapling[playwright]
playwright install chromium
# readability-lxml 已包含在 pyproject.toml 中
```
