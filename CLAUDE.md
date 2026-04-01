<!-- GSD:project-start source:PROJECT.md -->
## Project

**个人资讯系统**

一个个人资讯系统，帮助用户收集、订阅和组织来自互联网的信息来源。用户添加 RSS 订阅源或网站 URL，系统自动抓取内容并存储到本地 SQLite 数据库中，便于后续阅读和检索。

**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

### Constraints

- **Tech**: Python (CLI 工具)
- **Storage**: SQLite（单一数据库文件）
- **No API**: 纯本地应用，无后端服务
<!-- GSD:project-end -->

<!-- GSD:stack-start source:docs/technology-stack.md -->
## Technology Stack

See [docs/technology-stack.md](docs/technology-stack.md) for current dependencies.

Key technologies:
- **RSS/Feed**: feedparser, trafilatura
- **HTTP**: scrapling (Fetcher / AsyncFetcher)
- **Storage**: sqlite3, chromadb
- **Search**: sentence-transformers (embeddings), scikit-learn (BM25)
- **CLI**: click, rich

> **Note**: httpx has been replaced by scrapling.Fetcher
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:docs/Conventions.md -->
## Conventions

See [docs/](docs/) for project documentation.

### Release Process

See [docs/release.md](docs/release.md) for full workflow. **Critical steps**:

1. **Bump version FIRST** in `pyproject.toml`: `version = "1.2.2"`
2. Run pre-commit: `uv run pre-commit run --all`
3. Commit: `git add -A && git commit -m "Release v1.2.2"`
4. Create release: `gh release create v1.2.2 --title "v1.2.2" --notes "..."`
5. Verify: `curl -s pypi.org/pypi/feedship/json | grep version`

**Common failures**: Wrong version in pyproject.toml, using `git tag` instead of `gh release create`
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:docs/Architecture.md -->
## Architecture

See [docs/](docs/) for architecture diagrams and documentation.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

<!-- Agency:agents-routing -->
## Agency Agents 路由规则

本项目使用 agency-agents (~/.claude/agents/) 作为专家角色池。

### 自动路由规则

当检测到以下关键词时，自动使用对应专家角色：

| 触发条件 | 激活的 Agency Agent | 用途 |
|---------|-------------------|------|
| **安全、漏洞、威胁、审计** | `security-engineer` | 安全审查、威胁建模 |
| **数据库、查询、索引、SQL** | `database-optimizer` | Schema设计、查询优化 |
| **前端、React、Vue、UI、组件** | `frontend-developer` | UI实现、组件开发 |
| **后端、API、微服务、架构** | `backend-architect` | API设计、系统架构 |
| **性能、benchmark、优化** | `performance-benchmarker` | 性能测试与优化 |
| **测试、覆盖率、验证** | `code-reviewer` | 测试策略、代码审查 |
| **CI/CD、DevOps、部署** | `devops-automator` | 流水线、自动化 |
| **移动端、iOS、Android、React Native** | `mobile-app-builder` | 跨平台移动开发 |
| **AI、ML、模型、嵌入** | `ai-engineer` | 机器学习集成 |
| **代码审查、PR review** | `code-reviewer` | PR审查、质量把控 |
| **数据管道、ETL、数据仓库** | `data-engineer` | 数据基础设施 |

### 使用方式

在当前会话中直接说：
- "用 Security Engineer 视角审查这个 PR"
- "让 Database Optimizer 看看这个慢查询"
- "请 Backend Architect 评审这个 API 设计"

### GSD 集成

在 `/gsd:execute-phase` 执行期间，对应的 wave plan 会自动路由到专项专家。
