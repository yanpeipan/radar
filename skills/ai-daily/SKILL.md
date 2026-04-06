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

### Step 2: Get recent articles (last 2 days – covers timezone issues)
```bash
# Use dynamic dates (example for today)
SINCE=$(date -d '2 days ago' +%Y-%m-%d)
feedship article list --limit 333 --since $SINCE
```

### Step 3: Semantic search across key topics
Run the following searches to ensure comprehensive coverage:

```bash
# AI应用: ToB/ToC落地、Agent智能体、SaaS接入AI、商业模式创新
feedship search "AI应用 Agent智能体 SaaS AI商业模式 用户体验" --semantic --limit 200 --since $SINCE

# AI模型: 新模型发布、架构创新、训练突破
feedship search "LLM GPT Claude Gemini Llama MoE 开源模型" --semantic --limit 200 --since $SINCE

# AI基础设施: Agent框架、开发者工具、RAG
feedship search "Agent框架 RAG orchestration devtools 开发者工具" --semantic --limit 200 --since $SINCE

# 政策与安全: 监管、合规、安全
feedship search "AI政策 监管 合规 安全 隐私" --semantic --limit 200 --since $SINCE
```

### Step 4: Generate report sections (sequential file write)

Each section is generated and written to a separate file to avoid output truncation. Use bash to write files sequentially.

**Step 4a: Generate Section A**


```bash
DATE=$(date +%Y-%m-%d)
mkdir -p /tmp/ai-daily-$DATE
cat > /tmp/ai-daily/$DATE/section_a.md << 'EOF'
# AI 日报 DATE_PLACEHOLDER

## A. AI五层蛋糕
[按 REPORT_FORMAT.md 格式生成 AI五层蛋糕 内容]
EOF
```

**Step 4b: Generate Section B**
```bash
cat > /tmp/ai-daily/$DATE/section_b.md << 'EOF'
## B. 精选推荐
[按格式生成 精选推荐 内容]
EOF
```

**Step 4c: Generate Section C**
```bash
cat > /tmp/ai-daily/$DATE/section_c.md << 'EOF'
## C. 创业信号
[按格式生成 创业信号 内容]
EOF
```

**Step 4d: Generate Section D**
```bash
cat > /tmp/ai-daily/$DATE/section_d.md << 'EOF'
## D. 创作点
[按格式生成 创作点 内容]
EOF
```

**Step 4e: Generate Section E**
```bash
cat > /tmp/ai-daily/$DATE/section_e.md << 'EOF'
## E. 政策解读
[按格式生成 政策解读 内容]
EOF
```

**Step 4f: Generate Section F**
```bash
cat > /tmp/ai-daily/$DATE/section_f.md << 'EOF'
## F. 媒体热点
[按格式生成 媒体热点 内容]
EOF
```

**Step 4g: Send report in segments (avoid truncation)**
```bash
DATE=$(date +%Y-%m-%d)
# 替换日期占位符
sed -i '' "s/DATE_PLACEHOLDER/$DATE/g" /tmp/ai-daily-$DATE/section_*.md

# 分段发送 (每段包含2个section)
# 发送 Part 1: A + B
cat /tmp/ai-daily-$DATE/section_a.md /tmp/ai-daily-$DATE/section_b.md

# 发送 Part 2: C + D
cat /tmp/ai-daily-$DATE/section_c.md /tmp/ai-daily-$DATE/section_d.md

# 发送 Part 3: E + F
cat /tmp/ai-daily-$DATE/section_e.md /tmp/ai-daily-$DATE/section_f.md
```

**注意：** 分段发送时，每个 part 都会单独推送。如果 channel 支持更长的消息，可以合并发送。最终输出应包含完整日期。
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
