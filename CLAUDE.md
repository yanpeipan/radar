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
