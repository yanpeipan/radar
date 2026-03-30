---
status: resolved
trigger: "feed add 显示 'Added 0, updated 1 feed(s)' 但 metadata 没有被保存"
created: 2026-03-30T00:00:00Z
updated: 2026-03-30T00:00:00Z
---

## Current Focus
next_action: "已修复并验证"

## Symptoms
expected: 添加或更新 feed 时，应该保存 FeedMetaData（包含 feed_type 和 selectors）到数据库
actual: feed add 显示 "Added 0, updated 1 feed(s)"，但 selectors 被覆盖为 None
errors: 无错误信息
reproduction: python -m src.cli feed add https://openai.com/news/engineering/rss.xml
started: 未知，可能在最近的 FeedMetaData 重构后出现问题

## Eliminated
- hypothesis: "register_feed 没有传递 feed_meta 参数"
  evidence: "之前已修复，CLI 现在传递 feed_meta = FeedMetaData(feed_type=..., selectors=...)"
  timestamp: 2026-03-30T00:00:00Z

- hypothesis: "upsert_feed 没有更新 metadata 字段"
  evidence: "upsert_feed 的 UPDATE 语句包含 metadata = ?"
  timestamp: 2026-03-30T00:00:00Z

## Evidence
- timestamp: 2026-03-30T00:00:00Z
  checked: "src/cli/feed.py feed_add 函数"
  found: "两处 register_feed 调用都传递 feed_meta 参数 (lines 220-224, 247-251)"
  implication: "CLI 正确传递 feed_meta"

- timestamp: 2026-03-30T00:00:00Z
  checked: "src/application/feed.py register_feed 函数"
  found: "register_feed 创建 Feed 对象时设置 metadata=feed_meta_data.to_json() (line 144)"
  implication: "register_feed 正确将 FeedMetaData 转换为 JSON"

- timestamp: 2026-03-30T00:00:00Z
  checked: "src/storage/sqlite/impl.py upsert_feed 函数"
  found: "UPDATE 语句包含 metadata 字段 (line 432)"
  implication: "upsert_feed 在更新时包含 metadata"

- timestamp: 2026-03-30T00:00:00Z
  checked: "providers parse_feed 方法"
  found: "DiscoveredFeed.metadata 始终为 None，因为 providers 不设置它"
  implication: "feed.metadata.selectors 始终为 None"

- timestamp: 2026-03-30T00:00:00Z
  checked: "compute_link_selectors 函数调用"
  found: "compute_link_selectors 定义但从未被调用"
  implication: "selectors 从未被 discovery 过程填充"

- timestamp: 2026-03-30T00:00:00Z
  checked: "UPDATE 是否覆盖已有 selectors"
  found: "测试确认：已有 selectors=[\\"/news/\\"] 的 feed，更新后 selectors 变成 None"
  implication: "根因：CLI 使用 feed.metadata.selectors (始终为 None) 覆盖了已有 selectors"

## Resolution

### Root Cause
`register_feed` 在更新 feed 时，如果新传入的 `FeedMetaData` 没有 selectors（因为 `DiscoveredFeed.metadata` 始终为 None），就会用 `None` 覆盖数据库中已有的 selectors。

具体流程：
1. CLI 调用 `register_feed(feed.url, feed.title, weight, feed_meta)`
2. `feed_meta = FeedMetaData(feed_type=feed.feed_type, selectors=None)` 因为 `feed.metadata` 是 None
3. `upsert_feed` 执行 UPDATE，将 metadata 覆盖为 `{"feed_type": "rss"}` (没有 selectors)
4. 数据库中原有的 selectors 丢失

### Fix Applied
在 `register_feed` 中添加逻辑：如果新传入的 `feed_meta_data` 没有 selectors，则从数据库中读取已有的 selectors 并保留。

修改文件：`src/application/feed.py`
- 添加 `FeedMetaData` 到 imports
- 在 `register_feed` 函数中添加 selectors 保留逻辑

### Verification
测试确认修复有效：
- 更新前：`{"selectors": ["/news/"], "feed_type": "rss"}`
- 更新后：`{"selectors": ["/news/"], "feed_type": "rss"}` (selectors 保留)

所有测试通过：43 passed

### Files Changed
- `src/application/feed.py`: register_feed 函数添加 selectors 保留逻辑

verification: "测试通过：更新已有 selectors 的 feed 时 selectors 被正确保留"
files_changed: ["src/application/feed.py"]
