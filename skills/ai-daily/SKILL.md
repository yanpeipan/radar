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


### Step 2: Get recent articles (last 2 days – covers timezone issues)
```bash
# Use dynamic dates (example for today)
SINCE=$(date -d '2 days ago' +%Y-%m-%d)
feedship article list --limit 333 --since $SINCE
```

### Step 3: Generate report sections (按需搜索)

Each section is generated with its dedicated search to avoid context overflow. Search results are saved to files first.

**Step 3a: Generate Section A (AI五层蛋糕)**
```bash
DATE=$(date +%Y-%m-%d)
mkdir -p /tmp/ai-daily-$DATE
# AI应用 - 必须使用 --json 获取真实文章链接！
feedship search "Focusing on the full-stack AI ecosystem..." --semantic --limit 333 --json > /tmp/ai-daily-$DATE/search_a.json
# 提取链接用于报告
cat /tmp/ai-daily-$DATE/search_a.json | jq -r '.items[] | "\(.title) | \(.link)"' > /tmp/ai-daily-$DATE/links_a.txt

cat > /tmp/ai-daily-$DATE/section_a.md << 'EOF'
# AI 日报 DATE_PLACEHOLDER

## A. AI五层蛋糕
[按 REPORT_FORMAT.md 格式生成，必须使用 search_*.json 中的真实 article.link]
EOF
```

**Step 3b: Section B (精选推荐)**
```bash
# 必须使用 --json 获取真实文章链接！
feedship search "AI 热门 精选 推荐" --semantic --limit 333 --json > /tmp/ai-daily-$DATE/search_b.json
cat /tmp/ai-daily-$DATE/search_b.json | jq -r '.items[] | "\(.title) | \(.link)"' > /tmp/ai-daily-$DATE/links_b.txt
cat > /tmp/ai-daily-$DATE/section_b.md << 'EOF'
## B. 精选推荐
[按格式生成，必须使用 search_*.json 中的真实 article.link]
EOF
```

**Step 3c: Section C (创业信号)**
```bash
feedship search "融资 创业 投资 收购" --semantic --limit 333 --json > /tmp/ai-daily-$DATE/search_c.json
cat /tmp/ai-daily-$DATE/search_c.json | jq -r '.items[] | "\(.title) | \(.link)"' > /tmp/ai-daily-$DATE/links_c.txt
cat > /tmp/ai-daily-$DATE/section_c.md << 'EOF'
## C. 创业信号
[按格式生成，必须使用 search_*.json 中的真实 article.link]
EOF
```

**Step 3d: Section D (创作点)**
```bash
feedship search "AI创作 热门话题 趋势" --semantic --limit 333 --json > /tmp/ai-daily-$DATE/search_d.json
cat /tmp/ai-daily-$DATE/search_d.json | jq -r '.items[] | "\(.title) | \(.link)"' > /tmp/ai-daily-$DATE/links_d.txt
cat > /tmp/ai-daily-$DATE/section_d.md << 'EOF'
## D. 创作点
[按格式生成，必须使用 search_*.json 中的真实 article.link]
EOF
```

**Step 3e: Section E (政策解读)**
```bash
feedship search "AI政策 监管 合规 安全" --semantic --limit 333 --json > /tmp/ai-daily-$DATE/search_e.json
cat /tmp/ai-daily-$DATE/search_e.json | jq -r '.items[] | "\(.title) | \(.link)"' > /tmp/ai-daily-$DATE/links_e.txt
cat > /tmp/ai-daily-$DATE/section_e.md << 'EOF'
## E. 政策解读
[按格式生成，必须使用 search_*.json 中的真实 article.link]
EOF
```

**Step 3f: Section F (媒体热点)**
```bash
feedship search "AI社交热议 舆论焦点" --semantic --limit 333 --json > /tmp/ai-daily-$DATE/search_f.json
cat /tmp/ai-daily-$DATE/search_f.json | jq -r '.items[] | "\(.title) | \(.link)"' > /tmp/ai-daily-$DATE/links_f.txt
cat > /tmp/ai-daily-$DATE/section_f.md << 'EOF'
## F. 媒体热点
[按格式生成，必须使用 search_*.json 中的真实 article.link]
EOF
```

### Step 4: Auto-format sections (no AI content generation)

**关键：禁止 AI 生成新内容或标题，只做格式转换！**

用 Python 脚本直接格式化，避免 AI 幻觉：

```bash
DATE=$(date +%Y-%m-%d)
python3 << 'PYEOF'
import re

def format_section(lines, section_name):
    items = []
    for line in lines:
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) >= 2:
            title = parts[0].strip()
            link = parts[1].strip()
            if title and link and link != 'null':
                items.append((title, link))

    with open(f'/tmp/ai-daily-{DATE}/section_{section_name}.md', 'w') as f:
        f.write(f'## {section_name}\n\n')
        for i, (title, link) in enumerate(items, 1):
            safe_title = re.sub(r'[#*`]', '', title)
            f.write(f'{i}. {safe_title}\n')
            f.write(f'   来源：[**链接**]({link})\n\n')

for section, filename in [('A', 'links_a'), ('B', 'links_b'), ('C', 'links_c'),
                           ('D', 'links_d'), ('E', 'links_e'), ('F', 'links_f')]:
    try:
        with open(f'/tmp/ai-daily-{DATE}/{filename}.txt') as f:
            format_section(f.readlines(), section)
    except: pass

**Step 4g: Generate Editor's Note (主编导读)**
```bash
# 通读所有section文件，撰写高阶洞察
cat /tmp/ai-daily-$DATE/section_*.md > /tmp/ai-daily-$DATE/all_sections.txt

cat > /tmp/ai-daily-$DATE/editors_note.md << 'EOF'
**💡 主编导读 (Editor's Note)：**
[请基于以上全部内容，用第一性原理剖析今日资讯隐藏的"暗线"：底层模型发布如何倒逼应用层洗牌、某芯片法案如何影响基础设施投资逻辑、某监管动向如何重塑竞争格局等。150字左右，语气专业犀利，具备前瞻性。]
EOF
```

**Step 4h: Concatenate final report**
```bash
DATE=$(date +%Y-%m-%d)
# 替换日期占位符
sed -i '' "s/DATE_PLACEHOLDER/$DATE/g" /tmp/ai-daily-$DATE/section_*.md

# 合并：主编导读 + 全部sections
cat /tmp/ai-daily-$DATE/editors_note.md /tmp/ai-daily-$DATE/section_*.md

# 输出完整报告
cat /tmp/ai-daily-$DATE/section_*.md
```

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
