---
status: investigating
trigger: "summarize content-fetch: summarize 命令需要获取完整文章 content，数据库为空时应抓取 URL 并更新"
created: 2026-04-08T00:00:00Z
updated: 2026-04-08T00:00:00Z
---

## Current Focus
hypothesis: "process_article_llm() 只使用了 content or description，没有在 content 为空时抓取 URL"
test: "检查 process_article_llm 是否在 content 为空时调用 fetch_and_fill_article"
expecting: "如果 content 为空，应该先调用 fetch_and_fill_article 抓取 URL 获取完整内容"
next_action: "修改 process_article_llm 函数，在 content 为空时调用 fetch_and_fill_article"

## Symptoms
expected: "summarize 时如果 article.content 为空，应该抓取 article.link URL 获取完整内容，存入 content 字段，然后用 content 生成摘要"
actual: "当前 summarize 命令只使用了 RSS feed 提供的短 description 字段来生成摘要"
errors: []
reproduction: "uv run feedship summarize --id 'FPnvpL6zoc-kLH1G4HMkK' --force --json"
started: "v1.11 LLM 功能实现后存在的问题"

## Eliminated

## Evidence
- timestamp: 2026-04-08
  checked: "src/application/summarize.py process_article_llm()"
  found: "line 69: content = article.get('content') or article.get('description') or ''"
  implication: "只使用 content 或 description，如果两者都为空就直接返回错误，没有尝试抓取 URL"
- timestamp: 2026-04-08
  checked: "src/application/article_view.py"
  found: "存在 fetch_and_fill_article() 函数，可以根据 article_id 获取 link 并抓取内容"
  implication: "抓取逻辑已存在，但没有在 summarize 时调用"
- timestamp: 2026-04-08
  checked: "src/cli/summarize.py _summarize_url()"
  found: "URL 模式直接调用 fetch_url_content() 抓取内容并生成摘要"
  implication: "URL 模式没问题，问题在数据库文章模式"

## Resolution
root_cause: "process_article_llm() 在 content 为空时直接返回错误，而不是调用 fetch_and_fill_article() 抓取完整内容"
fix: "在 content 为空时调用 fetch_and_fill_article() 抓取 URL 内容，然后存入数据库并使用新 content 生成摘要"
verification: "待实现后测试"
files_changed: ["src/application/summarize.py"]
