---
version: 1.13.0
name: feedship-ai-daily
description: "Generate daily AI news digest from feedship subscriptions. Use when user wants today's news summary, daily briefing, periodic news recap, AI daily digest, ai daily, AI 日报, ai 日报, 生成简报, or 大模型日报. Reads existing feedship subscriptions, fetches latest articles, and generates a 6-section digest: (A) AI五层蛋糕, (B) 精选推荐, (C) 创业信号, (D) 创作点, (E) 政策解读, (F) 媒体热点. Requires feedship skill."
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

**Version:** 1.13.0
**For:** OpenClaw compatible agents
**Description:** Generate daily AI news digest from feedship subscriptions

## 1. Setup

Before using this skill, install feedship with required extras:

```bash
uv tool install 'feedship[ml,cloudflare]' --python 3.12 --force
```

Verify installation:

```bash
feedship --version
```

---

## 2. Channel Setup

### Telegram

1. **Create a bot**
   - Open Telegram, search for [@BotFather](https://t.me/BotFather)
   - Send `/newbot` and follow prompts
   - Copy the bot token (format: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`)

2. **Add channel to OpenClaw**
   ```bash
   openclaw channels add --channel telegram --token <YOUR_BOT_TOKEN>
   ```

3. **Get your chat ID**
   - Start a conversation with your bot and send any message
   - Run:
     ```bash
     curl -s https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates | jq '.message.chat.id'
     ```
   - Note the numeric chat ID (e.g., `123456789`)

4. **Verify channel**
   ```bash
   openclaw channels list
   ```

### 飞书 (Feishu)

1. **Create an app**
   - Go to [Feishu Open Platform](https://open.feishu.cn/app)
   - Click "Create App" → "Enterprise App"
   - Enable permissions: `im:message`, `im:message.receive_v1`
   - Get `App ID` and `App Secret`

2. **Add channel to OpenClaw**
   ```bash
   openclaw channels add --channel feishu --app-id <APP_ID> --app-secret <APP_SECRET>
   ```

3. **Verify channel**
   ```bash
   openclaw channels list
   ```

4. **Get your Open ID** – after adding, the channel list will show your destination ID.

---

## 3. Prerequisites Checklist

Before scheduling automated reports, verify:

- [ ] **OpenClaw gateway is running**
  ```bash
  openclaw gateway status
  ```
  Must show: `Runtime: running`
  If stopped: `openclaw gateway start`

- [ ] **At least one delivery channel is configured**
  ```bash
  openclaw channels list
  ```

- [ ] **feedship is installed with extras**
  ```bash
  feedship info --json | jq '.extras'
  ```
  Should include `ml` and `cloudflare`.
  If missing: `uv tool install 'feedship[ml,cloudflare]' --python 3.12 --force`

- [ ] **OpenClaw CLI is available**
  ```bash
  openclaw --version
  ```

---

## 4. Usage

### On‑Demand (Manual)

User says:
`"生成今日日报"`, `"今日新闻摘要"`, `"daily digest"`, `"AI日报"`

The agent will activate this skill and run the **Generate Daily Report** flow (see section 5).

### Automatic (Cron)

Schedule daily reports at 8:00 AM Beijing time.

#### Step 1: Verify your delivery channel
```bash
openclaw channels list
```
Note your channel type (`telegram`, `feishu`, `whatsapp`) and destination ID.

#### Step 2: Add the cron job
```bash
openclaw cron add \
  --name "feedship-ai-daily" \
  --agent feedship-ai-daily \
  --cron "0 8 * * *" \
  --tz Asia/Shanghai \
  --session isolated \
  --announce \
  --channel <your-channel> \
  --to <your-destination> \
  --timeout-seconds 900 \
  --message "使用 feedship-ai-daily skill 生成今日日报。先读取 ~/.openclaw/skills/ai-daily/SKILL.md 了解格式要求，然后严格遵循 A-F 六段式格式生成报告。"
```

**Important:**
- `--announce` is required for the report to be sent.
- `--session isolated` ensures a clean environment.
- The `--message` tells the agent to read the skill instructions (cron jobs do not auto‑load skill files).

#### Step 3: Verify the cron job
```bash
openclaw cron list
```
Look for `feedship-ai-daily` with `session: isolated` and `announce: true`.

#### Step 4: Test immediately (optional)
```bash
openclaw cron run <job-id>
```
Find `<job-id>` from `openclaw cron list`.

---

## 5. Generate Daily Report

**Core principle:** Process **all** available articles systematically. Do not manually select 5‑8 articles. Use clustering and batch processing.

### Step 1: Fetch latest articles
```bash
feedship fetch --all
```

### Step 2: Get recent articles (last 3 days – covers timezone issues)
```bash
# Use dynamic dates (example for today)
SINCE=$(date -d '3 days ago' +%Y-%m-%d)
UNTIL=$(date +%Y-%m-%d)
feedship article list --limit 333 --since $SINCE --until $UNTIL
```

### Step 3: Semantic search across key topics
Run the following searches to ensure comprehensive coverage:

```bash
# Models & foundation
feedship search "LLM GPT Claude Gemini Llama MoE 多模态 开源模型" --semantic --limit 333 --since $SINCE

# Applications & products
feedship search "AI应用 AI PMF MRR ARR AI SaaS OPC 创业 投资 startup funding" --semantic --limit 333 --since $SINCE

# Infrastructure & tools
feedship search "Agent框架 Autonomous Agent workflows RAG orchestration devtools" --semantic --limit 333 --since $SINCE

# Policy & regulation
feedship search "AI政策 监管 合规 法律 regulation compliance" --semantic --limit 333 --since $SINCE

# Security & ethics
feedship search "AI安全 伦理 隐私 争议 safety ethics" --semantic --limit 333 --since $SINCE
```

### Step 4: Cluster and generate report

1. **Cluster** articles by semantic similarity into topics.
2. **Count** articles per topic to identify significance.
3. **Map** clusters to the six sections:

| Section | Name | Mapping |
|---------|------|---------|
| A | AI五层蛋糕 | AI应用, AI模型, AI基础设施, 芯片, 能源 (with #融资/#并购/#趋势 tags) |
| B | 精选推荐 | Top 10‑15 articles across all clusters, grouped by topic |
| C | 创业信号 | High-leverage tools + conditional business teardown |
| D | 创作点 | Content angles and story ideas |
| E | 政策解读 | Policy & regulation |
| F | 媒体热点 | Viral discussions and media trends |

---

## 6. Report Format

**Every report MUST contain exactly 6 sections (A–F) in order.**

See the full format specification in `~/.openclaw/skills/ai-daily/REPORT_FORMAT.md` (if present).
Quick reference:

| Section | Name | Required content |
|---------|------|------------------|
| A | AI五层蛋糕 | For each layer: AI-generated summary + at least 2 source links |
| B | 精选推荐 | 5‑8 articles with title, one‑sentence summary, link; merge hot topics |
| C | 创业信号 | High-leverage tools (max 3) + conditional business teardown (触发条件: 融资>$10M OR 爆款应用 OR 技术栈可推测) |
| D | 创作点 | Story angles and content inspiration for creators |
| E | 政策解读 | Regulations, compliance developments, impact analysis |
| F | 媒体热点 | Highly discussed AI topics on social/ traditional media |

**Example snippet:**

```markdown
# AI 日报 2025-12-25

## A. AI五层蛋糕
### 1. AI应用
- 摘要：今日头条...
- 来源：[标题](链接) | [标题2](链接2)
...
```

---

## 7. Tips

- If no articles are found for today, say "今日无新文" and suggest checking yesterday.
- Use `feedship feed list -v` to see feed weights.
- For long articles, read the summary via `feedship article view <id>` then extract key points.
- Maintain diversity – avoid clustering all picks into the same topic.
- Diagnostic info: `feedship info --json`

---

## 8. Configuration

### Ranking Criteria

By default, articles in Section C are ranked by feed weight (权重).

- **Option 1 – Feed weight (default)**
  Sort by weight descending. Check weights with `feedship feed list -v`.

- **Option 2 – Views**
  Sort by `阅读量` descending (higher views indicate more interest).

- **Option 3 – Semantic relevance**
  ```bash
  feedship search "your keywords" --semantic --limit 10 --since YYYY-MM-DD
  ```

### Feed Weight Reference

Weights range from 0.1 (low priority) to 1.0 (high priority).

---

## 9. Troubleshooting

| Problem | Possible cause | Solution |
|---------|----------------|---------|
| Cron never fires | Gateway not running | `openclaw gateway start` |
| No output delivered | Missing `--announce` or channel misconfigured | Re‑add cron with `--announce`; verify `openclaw channels list` |
| `feedship: command not found` | Isolated session PATH issue | Ensure feedship is installed with `uv tool install`; restart gateway: `openclaw gateway restart` |
| Empty report | No new articles or fetch failed | Check feeds: `feedship feed list -v`; manual `feedship fetch --all` to see errors |
| Hugging Face model download fails | Network / mirror issue | Set `HF_ENDPOINT=https://hf-mirror.com` before running |

### Diagnostic Cron Job

To test if the isolated session can run feedship:

```bash
openclaw cron add \
  --name "diagnostic" \
  --agent feedship-ai-daily \
  --cron "0 8 * * *" \
  --session isolated \
  --announce \
  --message "Check feedship: feedship --version"
```

---

## 10. Environment Variables

- `HF_ENDPOINT` – Set Hugging Face mirror (e.g., `https://hf-mirror.com`)
- `FEEDSHIP_CACHE_DIR` – Custom cache directory (default: `~/.cache/feedship`)
- `OPENCLAW_HOME` – OpenClaw config directory (default: `~/.openclaw`)

---

**Changelog:**
- 1.13.0: Fixed YAML syntax, updated skill path to `~/.openclaw/skills/`, improved date handling, added troubleshooting table, clarified cron instructions.
- 1.12.0: Initial version.
