# Requirements: Feedship OpenClaw Skills

**Defined:** 2026-04-03
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1 Requirements

### Skill Enhancement

- [ ] **SKILL-01**: 修复 feedship SKILL.md 中 YAML pipe 字符（`|`）未引号化问题
- [ ] **SKILL-02**: 修复 feedship SKILL.md 中 YAML 冒号（`:`）未引号化问题
- [ ] **SKILL-03**: 移除 feedship SKILL.md 中非标的 `compatibility` 字段
- [ ] **SKILL-04**: 修复 ai-daily SKILL.md 中 YAML pipe/冒号未引号化问题
- [ ] **SKILL-05**: 验证并修正 metadata 命名空间格式（`openclaw` vs `clawdbot`）

### feedship Skill Update

- [ ] **FEED-01**: 补充 `feedship info` 命令文档（版本、配置、存储、JSON 输出）
- [ ] **FEED-02**: 补充 `--json` 输出标志文档到所有支持命令
- [ ] **FEED-03**: 更新 feedship SKILL.md 版本到 1.5

### ai-daily Skill Update

- [ ] **AID-01**: 添加 `feedship info --json` 诊断提示到 ai-daily skill
- [ ] **AID-02**: 更新 ai-daily SKILL.md 版本

### Publishing

- [ ] **PUBLISH-01**: 运行 `package_skill.py` 验证两个 skills 通过
- [ ] **PUBLISH-02**: 发布 feedship skill 到 clawhub
- [ ] **PUBLISH-03**: 发布 ai-daily skill 到 clawhub

## v2 Requirements

(None)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-language SKILL variants | v1 focused on English SKILL.md |
| Video walkthroughs | v1 focused on text documentation |
| Interactive examples | v1 focused on static documentation |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SKILL-01 | Phase 10 | Pending |
| SKILL-02 | Phase 10 | Pending |
| SKILL-03 | Phase 10 | Pending |
| SKILL-04 | Phase 10 | Pending |
| SKILL-05 | Phase 10 | Pending |
| FEED-01 | Phase 10 | Pending |
| FEED-02 | Phase 10 | Pending |
| FEED-03 | Phase 10 | Pending |
| AID-01 | Phase 10 | Pending |
| AID-02 | Phase 10 | Pending |
| PUBLISH-01 | Phase 10 | Pending |
| PUBLISH-02 | Phase 10 | Pending |
| PUBLISH-03 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-03*
*Last updated: 2026-04-03 after roadmap creation*
