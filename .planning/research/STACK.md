# Stack Research: OpenClaw Skill Publishing

**Domain:** Claude Code / OpenClaw skill publishing to clawhub
**Researched:** 2026-04-03
**Confidence:** MEDIUM

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| SKILL.md | 1.0 | Skill definition format | Required file format for OpenClaw/clawhub skill registration |
| YAML frontmatter | 1.1+ | Metadata specification | Standard for skill frontmatter; parsable by OpenClaw runtime |
| Anthropic SDK | beta | Skill publishing API | Official API for creating/managing skills on clawhub |
| uv | latest | Package installation | Recommended installer for Python-based skills |

### Skill Format (SKILL.md)

The SKILL.md file uses YAML frontmatter followed by markdown content:

```yaml
---
name: skill-name
description: |
  One-line summary. Use when [trigger phrases].
  Commands: cmd1, cmd2, cmd3.
compatibility: Install with uv or pipx
metadata:
  openclaw:
    requires:
      bins:
        - uv
      cron:
        syntax: cron([minute,] [hour,] [day-of-month,] [month,] [day-of-week])
        default: "0 8 * * *"
        description: "Optional cron schedule description"
---
```

### Required Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier (kebab-case recommended) |
| `description` | Yes | Trigger phrases and command summary for agent routing |
| `compatibility` | Recommended | Installation instructions |
| `metadata.openclaw.requires.bins` | For CLI tools | Required binary executables |

### Optional Frontmatter Fields

| Field | When to Use | Example |
|-------|-------------|---------|
| `metadata.openclaw.cron` | Scheduled skills | Daily digest at 8 AM |
| `homepage` | External project pages | Project GitHub URL |
| `metadata.clawdbot` | Alternative format | Contains `emoji`, `requires`, `install` |

### Publishing Methods

#### Method 1: Anthropic SDK (Recommended for API-based publishing)

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

const skill = await client.beta.skills.create({
  display_title: 'Feedship',
  files: ['skills/feedship/'],  // Directory containing SKILL.md
});
```

#### Method 2: clawhub CLI

No CLI tool found installed. The registry is `https://clawhub.ai`.

#### Method 3: Manual via clawhub.ai

1. Create skill directory with SKILL.md
2. Publish via web interface at clawhub.ai

### Versioning

Skills use semantic versioning in frontmatter `version` field:

```yaml
---
name: feedship
version: 1.0.0
---
```

Version is tracked in `.clawdhub/origin.json` after installation:

```json
{
  "version": 1,
  "registry": "https://clawhub.ai",
  "slug": "feedship",
  "installedVersion": "1.0.0",
  "installedAt": 1774976888127
}
```

### Dependencies Specification

#### Binary Requirements (`metadata.openclaw.requires.bins`)

```yaml
metadata:
  openclaw:
    requires:
      bins:
        - uv
        - feedship
```

#### Install Instructions (`metadata.clawdbot` alternative format)

```yaml
metadata:
  clawdbot:
    emoji: "📰"
    requires:
      bins: ["blogwatcher"]
    install:
      - id: go
        kind: go
        module: github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest
        bins: ["blogwatcher"]
        label: "Install blogwatcher (go)"
```

## Existing Skill Structure in feedship

Current skills in `/Users/y3/feedship/skills/`:

- `feedship/SKILL.md` - Uses `metadata.openclaw.requires.bins: [uv]`
- `ai-daily/SKILL.md` - Uses `metadata.openclaw.requires.bins: [uv]` with cron support

Both skills are already in the correct format for clawhub publishing.

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Non-YAML frontmatter | OpenClaw parser expects YAML | Proper YAML block |
| Missing `name` field | Skill cannot be registered | Include `name` in frontmatter |
| Missing `description` | Agent cannot route to skill | Include trigger phrases in description |
| Hardcoded absolute paths | Not portable | Relative paths or environment variables |
| Outdated SDK versions | Missing beta features | Use latest `@anthropic-ai/sdk` beta |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `@anthropic-ai/sdk` | Node.js 18+ | Required for beta skills API |
| YAML | Any | Standard parsing |
| uv | Python 3.8+ | Recommended Python package installer |

## Skill Directory Structure

```
skills/
├── feedship/
│   └── SKILL.md          # Required: skill definition
├── ai-daily/
│   └── SKILL.md          # Required: skill definition
```

Optional additional files (not required for basic publishing):
- `references/` - Additional documentation
- `hooks/` - OpenClaw hook handlers
- `src/` - Skill source code

## Publishing Checklist

- [ ] SKILL.md has valid YAML frontmatter with `name` and `description`
- [ ] `description` includes trigger phrases for agent routing
- [ ] `metadata.openclaw.requires.bins` lists all required binaries
- [ ] Version is updated in frontmatter
- [ ] Content is tested with OpenClaw-compatible agent

## Sources

- `/Users/y3/feedship/skills/feedship/SKILL.md` - Existing skill format (HIGH confidence)
- `/Users/y3/feedship/skills/ai-daily/SKILL.md` - Cron metadata example (HIGH confidence)
- `/Users/y3/clawd/skills/feedship/.clawdhub/origin.json` - clawhub registry tracking (HIGH confidence)
- `/Users/y3/.claude/skills/blogwatcher/SKILL.md` - Alternative clawdbot format (HIGH confidence)
- Anthropic SDK `skills.d.ts` - API types for beta skills API (HIGH confidence)
- `/Users/y3/.claude/skills/gstack/*/SKILL.md` - Extended skill format examples (HIGH confidence)

---
*Stack research for: OpenClaw skill publishing*
*Researched: 2026-04-03*
