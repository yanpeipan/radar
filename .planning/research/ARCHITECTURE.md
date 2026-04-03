# Architecture Research

**Domain:** OpenClaw Skill Publishing for Claude Code Agent
**Researched:** 2026-04-03
**Confidence:** HIGH

## Executive Summary

OpenClaw skills are skill modules that extend Claude Code agents' capabilities. Skills are folders containing a `SKILL.md` file with markdown documentation and YAML frontmatter declaring runtime requirements. Agents discover and invoke skills based on natural language matching against the skill's `description` field. Published skills are registered on ClawHub (clawhub.ai), OpenClaw's public skills registry.

## OpenClaw Skill Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code Agent                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  User Chat  │  │  Skill      │  │  Tool       │          │
│  │  Input      │  │  Matcher     │  │  Executor   │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                │                │                  │
│         └────────────────┴────────────────┘                  │
│                          │                                   │
├──────────────────────────┼──────────────────────────────────┤
│                 Skill Discovery Layer                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Local: ~/.openclaw/skills/ or <project>/skills/    │    │
│  │  Remote: ClawHub Registry (clawhub.ai)              │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Skill Publisher                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  clawhub    │  │  openclaw/  │  │  .clawhub/  │          │
│  │  CLI        │  │  skills     │  │  lock.json  │          │
│  │  publish    │  │  repo       │  │  origin.json│          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Skill Folder Structure

```
<skill-name>/
├── SKILL.md              # Required: skill documentation + frontmatter
├── references/           # Optional: supporting documentation
│   └── *.md
├── .clawhub/             # Optional: CLI metadata (gitignored)
│   └── origin.json       # Published origin tracking
└── .gitignore            # Optional: also honored by ClawHub
```

### SKILL.md Format

**Required:**
- `SKILL.md` (or `skill.md`)
- YAML frontmatter with `name` and `description`

**Frontmatter Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Skill identifier (lowercase, URL-safe) |
| `description` | string | Summary for UI/search; agent matching uses this |
| `version` | string | Semantic version (optional, ClawHub manages) |
| `metadata.openclaw.requires.env` | string[] | Required environment variables |
| `metadata.openclaw.requires.bins` | string[] | Required CLI binaries |
| `metadata.openclaw.requires.anyBins` | string[] | CLI where at least one must exist |
| `metadata.openclaw.requires.config` | string[] | Config file paths |
| `metadata.openclaw.primaryEnv` | string | Main credential env var |
| `metadata.openclaw.always` | boolean | If true, skill always active |
| `metadata.openclaw.cron` | object | Cron schedule for automatic triggering |
| `metadata.openclaw.install` | array | Dependency install specs |

**Example Frontmatter:**

```yaml
---
name: feedship
description: Manage RSS/Atom feeds, subscribe to websites, search and read articles. Use when working with feeds, RSS, Atom, subscribing to content sources, managing an information pipeline, or fetching articles from subscribed feeds.
compatibility: Install with pipx (recommended): `pipx install 'feedship[cloudflare,ml]'`
metadata:
  openclaw:
    requires:
      bins:
        - uv
    cron:
      syntax: cron([minute,] [hour,] [day-of-month,] [month,] [day-of-week])
      default: "0 8 * * *"
      description: "Generate daily AI news digest every day at 8 AM"
---
```

### Skill Discovery and Invocation

**Discovery Mechanism:**
1. Agent analyzes user input
2. Matches against skill `description` fields using natural language
3. Skills with matching descriptions are considered for invocation
4. Agent invokes matched skills to fulfill user request

**Invocation Flow:**
```
User: "Fetch my RSS feeds and show recent articles"
    │
Agent identifies intent -> "RSS feed management, article retrieval"
    │
Skill matcher finds feedship skill (description match)
    │
Agent reads SKILL.md, executes documented commands
    │
Commands executed via CLI (feedship fetch --all, feedship article list)
```

**Priority Order for Skill Loading:**
1. Workspace: `<project>/skills/`
2. Local: `~/.openclaw/skills/`
3. Bundled: Built-in agent skills

### ClawHub Publishing

**Publish Flow:**
```bash
# Via CLI
clawhub publish <skill-folder> --slug <slug> --version 1.0.0

# Via sync (auto-publish changed skills)
clawhub sync
```

**Install Flow:**
```bash
# Via CLI
clawhub install <slug>

# Manual
cp -r <skill-folder> ~/.openclaw/skills/
```

**ClawHub Registry Endpoints:**
- API Base: `https://clawhub.ai`
- Search: `GET /api/v1/search?q=...`
- Skill detail: `GET /api/v1/skills/{slug}`
- Download: `GET /api/v1/download?slug=...&version=...`

## Feedship Skill Integration Points

### Current State

**Existing Skills in `/skills/`:**
- `feedship/` - RSS/feed management skill
- `ai-daily/` - AI daily digest generation skill

**feedship Skill:**
- Single `SKILL.md` file (6.5KB)
- Documents all CLI commands: feed add/list/remove, fetch, article list/view/open/related, search, discover
- Declares `uv` as required binary
- Provides Rich table/panel output formats

**ai-daily Skill:**
- Single `SKILL.md` file
- Depends on feedship skill
- Provides cron trigger configuration
- Documents 3-section daily digest format

### Integration Points for Enhancement

| Enhancement | Location | Required Change |
|-------------|----------|------------------|
| Add `--json` output documentation | feedship SKILL.md | Document JSON output flag |
| Add `info` command documentation | feedship SKILL.md | Add INFO-01 through INFO-07 commands |
| Skill invocation triggers | feedship SKILL.md | Update description with new command keywords |
| Skill versioning | feedship SKILL.md | Add version field to frontmatter |
| Dependency declarations | feedship SKILL.md | Update `requires.bins` if new dependencies |

### Build Order Considerations

1. **First:** Update feedship SKILL.md with `info` command documentation and `--json` output
2. **Second:** Update ai-daily SKILL.md if new feedship commands affect digest flow
3. **Third:** Publish to ClawHub via `clawhub publish` or `clawhub sync`
4. **Fourth:** Verify skill discoverability on clawhub.ai

## Anti-Patterns

### Anti-Pattern 1: Incomplete Metadata

**What people do:** Not declaring required binaries/env vars in frontmatter
**Why it's wrong:** ClawHub security analysis flags mismatches; users don't know prerequisites
**Do this instead:** Always declare all `requires.env`, `requires.bins`, and `requires.config`

### Anti-Pattern 2: Vague Description

**What people do:** Generic descriptions like "A useful skill"
**Why it's wrong:** Agent cannot match to user intent; skill won't be invoked
**Do this instead:** Include trigger phrases: "Use when working with...", "Helpful for...", specific commands

### Anti-Pattern 3: Missing Installation Instructions

**What people do:** Not including install commands in SKILL.md
**Why it's wrong:** Users cannot install skill dependencies
**Do this instead:** Include `Installation` section with pipx/uv commands

### Anti-Pattern 4: Version Mismatch

**What people do:** Publishing without bumping version
**Why it's wrong:** ClawHub requires new version for each publish
**Do this instead:** Increment semver before each publish

## Scaling Considerations

| Scale | Skill Architecture |
|-------|-------------------|
| 1-10 skills | Simple folder structure, manual publish |
| 10-100 skills | Use `clawhub sync` for batch publishing |
| 100+ skills | Consider skill organization by category |

**Skill Bundle Limits:**
- Total bundle size: 50MB
- Embedding includes SKILL.md + up to ~40 non-.md files
- Only text-based files accepted (JSON, YAML, TOML, Markdown, SVG)

## Sources

- [ClawHub Skill Format Documentation](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md) - HIGH confidence (official documentation)
- [ClawHub Architecture Documentation](https://github.com/openclaw/clawhub/blob/main/docs/architecture.md) - HIGH confidence (official documentation)
- [ClawHub API Documentation](https://github.com/openclaw/clawhub/blob/main/docs/api.md) - HIGH confidence (official documentation)
- [VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills) - MEDIUM confidence (community collection)

---
*Architecture research for: OpenClaw Skill Publishing for feedship*
*Researched: 2026-04-03*
