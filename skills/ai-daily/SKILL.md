---
name: feedship-ai-daily
description: Generate daily AI news digest from feedship subscriptions. Use when user wants today's news summary, daily briefing, periodic news recap, AI daily digest, ai daily, AI 日报, ai 日报, 生成简报, or 大模型日报. Reads existing feedship subscriptions, fetches latest articles, and generates a 3-section digest: (A) Today's new articles with summaries, (B) Hot topics clustering, (C) Featured picks by feed weight. Requires feedship skill.
compatibility: Requires uv and feedship CLI. Install with: uv pip install feedship
metadata:
  openclaw:
    requires:
      bins:
        - uv
    cron:
      syntax: cron([minute,] [hour,] [day-of-month,] [month,] [day-of-week])
      default: "0 8 * * *"  # Daily at 8:00 AM
      description: "Generate daily AI news digest every day at 8 AM"
---

# AI 日报 (Feedship AI Daily)

**Version:** 1.0
**For:** OpenClaw compatible agents
**Description:** Generate daily AI news digest from feedship subscriptions

## Setup

Before using this skill, install feedship:

```bash
uv pip install feedship
```

Verify installation: `feedship --version`

---

## Usage

### On-Demand

User says: "生成今日日报"、"今日新闻摘要"、"daily digest"

Agent activates this skill and runs the Generate Daily Report flow.

### Automatic (Cron)

Configure in OpenClaw agent with cron trigger:

```
cron: 0 8 * * *
```

This runs daily at 8:00 AM. The agent activates this skill automatically.

---

## Generate Daily Report

Execute these steps in order:

### Step 1: Fetch Latest Articles

```bash
# Fetch all subscribed feeds for latest articles
feedship fetch --all
```

Wait for fetch to complete before proceeding.

### Step 2: Get Today's Articles

Get today's date in YYYY-MM-DD format.

```bash
feedship article list --limit 100 --since YYYY-MM-DD
```

Filter to articles actually published today (check the date column in output).

Then use semantic search to focus on current themes:

```bash
feedship search "AI LLM GPT machine learning" --semantic --limit 33 --since YYYY-MM-DD
```

### Step 4: Generate 3-Section Report

Read full content for articles you want to summarize:

```bash
feedship article view <article-id>
```

---

## Report Format

### Section A: 今日新文 (Today's New Articles)

List all articles published today with 1-2 sentence summary each.

Format:

```
## 今日新文

| 来源 | 标题 | 摘要 |
|------|------|------|
| Feed Name | Article Title | 1-2 sentence summary |
```

- Include all articles from today
- Summaries should capture the key insight or news
- Skip articles with no meaningful content

### Section B: 热点话题 (Hot Topics)

Cluster today's articles into 3-5 topic groups based on content similarity.

Format:

```
## 热点话题

### Topic Name
- [n] 篇相关
- Key theme or finding from this cluster

### Another Topic
- [n] 篇相关
- Key theme or finding
```

- Group semantically similar articles together
- Name each topic by its main theme
- Count articles per topic
- Extract the most important insight from each topic

### Section C: 精选推荐 (Featured Picks)

Select top 5-8 articles based on feed weight priority.

Format:

```
## 精选推荐

1. **[Article Title]**
   来源: Feed Name | 权重: 0.5
   推荐理由: Why this is important

2. **[Article Title]**
   来源: Feed Name | 权重: 0.3
   推荐理由: Why this matters
```

- Prioritize high-weight feeds (check with `feedship feed list -v`)
- Select diverse topics across selections
- Include specific recommendation reason

---

## Complete Example Output

```
# AI 日报 — 2026-04-01

## 今日新文

| 来源 | 标题 | 摘要 |
|------|------|------|
| Google AI Blog | New Model Achieves SOTA | Introduces novel architecture reducing compute by 40% |
| OpenAI News | GPT-5 Release | New version features extended context and reasoning |
| ... | ... | ... |

## 热点话题

### LLM 新模型发布
- [4] 篇相关
- 多家机构本周发布新模型，竞争激烈

### AI 安全与对齐
- [3] 篇相关
- 新研究关注长上下文安全性问题

## 精选推荐

1. **[Google AI Blog] New Model Achieves SOTA**
   来源: Google AI Blog | 权重: 0.5
   推荐理由: 技术突破，值得关注

2. **[OpenAI News] GPT-5 Release**
   来源: OpenAI News | 权重: 0.5
   推荐理由: 重要版本更新

...
```

---

## Tips

- If no articles found today, say "今日无新文" and suggest checking yesterday
- If feedship not installed, install first: `uv pip install feedship`
- Use `feedship feed list -v` to see feed weights
- For long articles, read summary via `feedship article view <id>` then select key points
- Diversity matters: don't cluster all picks into same topic
