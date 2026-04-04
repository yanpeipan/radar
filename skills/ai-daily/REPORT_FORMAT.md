# AI 日报报告格式

**MANDATORY: Every report MUST contain exactly these 4 sections in order. Do not skip, combine, or omit any section.**

---

## Section A: AI五层蛋糕 (AI Stack)

Categorize articles into the five-layer framework: AI应用 → AI模型 → AI基础设施 → 芯片 → 能源. Each sub-group uses topic summary format.

**Format:**

```
## A. AI五层蛋糕

### AI应用
1. 多模态AI应用加速落地，Copilot等产品持续迭代
   [2]篇来源：[**AI Weekly**](https://aiweekly.com), [**TechCrunch**](https://techcrunch.com)

### AI模型
1. 多机构发布新模型，LLM竞争进入新阶段
   [2]篇来源：[**Google AI Blog**](https://blog.google/ai), [**OpenAI News**](https://openai.com)

### AI基础设施
1. 新研究挑战传统scaling laws，模型训练方式可能需要重新思考
   [1]篇来源：[**AI Weekly**](https://aiweekly.com)

### 芯片
1. GPU供应持续紧张，定制芯片成为新方向
   [1]篇来源：[**Reuters**](https://reuters.com)

### 能源
1. AI耗电问题引发关注，大厂投资可再生能源
   [1]篇来源：[**TechCrunch**](https://techcrunch.com)
```

**Rules:**
- Classify each article into one of the five layers
- Within each layer, further group semantically similar articles together
- Each sub-group: header with layer name, then numbered topic themes with count + linked sources
- Order sub-groups by feed weight (评分), highest first

---

## Section B: 精选推荐 (Featured Picks)

Combine top articles with topic clustering: select 5-8 top ranked articles and group semantically similar ones together.

**Format:**

```
## B. 精选推荐

### Topic Name
1. [**Article Title**](https://example.com/article)
   来源: Feed Name | 权重: 0.5 | 阅读量: 1234
   推荐理由: Why this is important

2. [**Article Title**](https://example.com/article)
   来源: Feed Name | 权重: 0.3 | 阅读量: 890
   推荐理由: Why this matters

### Another Topic
1. [**Article Title**](https://example.com/article)
   来源: Feed Name | 权重: 0.4 | 阅读量: 567
   推荐理由: Key insight
```

**Rules:**
- Group semantically similar articles into topic clusters
- Rank within each cluster by feed weight (权重) or 阅读量 (views)
- Order clusters by total weight of articles (highest first)
- Include specific recommendation reason for each article

---

## Section C: 创业信号 (Startup Signals)

Detect funding news, acquisitions, and trend opportunities from existing articles using pattern-based detection.

**Format:**

```
## E. 创业信号

### 融资动态
- [n] 篇相关
- [Source] Article Title — X公司完成Y轮融资，金额Z百万美元

### 收购并购
- [n] 篇相关
- [Source] Article Title — A公司收购B公司，拓展C市场

### 趋势机会
- [n] 篇相关
- [Source] Article Title — 新兴趋势：X技术进入Y行业
```

**Key patterns to detect:**
- Funding: "raised", "Series", "closed round", "million"
- Acquisitions: "acquired", "acquisition", "acquire"
- Trends: "launching", "entering", "expanding to", "new capability"

**Note:** Sections E and F use existing article data from Section A — no new feeds or APIs needed.

---

## Section D: 创作点 (Content Angles)

Extract story angles and trending topics for content creation from existing articles.

**Format:**

```
## E. 创作点

### 可写主题
- [n] 篇相关
- 主题：Why X is reshaping Y industry
- 来源：[**Article1**](https://example.com/1), [**Article2**](https://example.com/2)

### 热门角度
- [n] 篇相关
- 角度：How to build in X space (step-by-step)
- 来源：[**Article3**](https://example.com/3)

### 争议性话题
- [n] 篇相关
- 话题：X的局限性 — 争议焦点
- 来源：[**Article4**](https://example.com/4), [**Article5**](https://example.com/5)
```

**Key patterns to detect:**
- Story angles: "why X matters", "the future of", "how to"
- Trending: "viral", "trending", "breaking"
- Controversial: "debate", "critics say", "controversial"
- Actionable: "X steps to", "lessons from"

---

## Complete Example Output

```
# AI 日报 — 2026-04-01

## A. AI五层蛋糕

### AI应用
1. 多模态AI应用加速落地，Copilot等产品持续迭代
   [3]篇来源：[**AI Weekly**](https://aiweekly.com), [**TechCrunch**](https://techcrunch.com), [**Reuters**](https://reuters.com)

### AI模型
1. 多机构发布新模型，LLM竞争进入新阶段
   [2]篇来源：[**Google AI Blog**](https://blog.google/ai), [**OpenAI News**](https://openai.com)

### AI基础设施
1. 新研究挑战传统scaling laws，模型训练方式可能需要重新思考
   [1]篇来源：[**AI Weekly**](https://aiweekly.com)

### 芯片
1. GPU供应持续紧张，定制芯片成为新方向
   [1]篇来源：[**Reuters**](https://reuters.com)

### 能源
1. AI耗电问题引发关注，大厂投资可再生能源
   [1]篇来源：[**TechCrunch**](https://techcrunch.com)

## B. 精选推荐

1. [**Google AI Blog] New Model Achieves SOTA**](https://blog.google/ai/new-model)
   来源: Google AI Blog | 权重: 0.5 | 阅读量: 1234
   推荐理由: 技术突破，计算效率提升40%

2. [**OpenAI News] GPT-5 Release**](https://openai.com/news/gpt-5)
   来源: OpenAI News | 权重: 0.5 | 阅读量: 1890
   推荐理由: 重要版本更新，支持更长上下文

3. [**AI Weekly] Multimodal Advances**](https://aiweekly.com/multimodal)
   来源: AI Weekly | 权重: 0.4 | 阅读量: 980
   推荐理由: 多模态技术成熟，应用场景扩展

## D. 热点话题

### LLM 新模型发布
- [4] 篇相关
- 多家机构本周发布新模型，竞争激烈

### AI 安全与对齐
- [3] 篇相关
- 新研究关注长上下文安全性问题

### 模型效率优化
- [2] 篇相关
- 新技术降低推理成本，提升效率

## D. 创业信号

### 融资动态
- [1] 篇相关
- [AI Weekly] LLM Efficiency — X公司完成A轮融资，金额50百万美元

### 收购并购
- [1] 篇相关
- [AI Weekly] Multimodal Advances — Y公司收购Z公司，拓展视觉市场

### 趋势机会
- [2] 篇相关
- [Google AI Blog] New Model Achieves SOTA — 新兴趋势：小型化模型进入移动端

## E. 创作点

### 可写主题
- [2] 篇相关
- 主题：Why small models are the future of edge AI
- 来源：[**Google AI Blog**](https://blog.google/ai), [**AI Weekly**](https://aiweekly.com)

### 热门角度
- [1] 篇相关
- 角度：How to fine-tune models on limited hardware
- 来源：[**AI Weekly**](https://aiweekly.com)

### 争议性话题
- [1] 篇相关
- 话题：GPT-5的长上下文是否值得额外成本 — 争议焦点
- 来源：[**OpenAI News**](https://openai.com)
```
