# Project Research Summary

**Project:** OpenClaw Skill Publishing for feedship CLI
**Domain:** Claude Code skill packaging and publishing
**Researched:** 2026-04-03
**Confidence:** MEDIUM

## Executive Summary

OpenClaw skills are markdown-based skill modules that extend Claude Code agents. Skills consist of a `SKILL.md` file with YAML frontmatter declaring runtime requirements (binaries, environment variables) and markdown documentation. Agents discover skills by natural language matching against the skill's `description` field, then execute documented CLI commands. Publishing to ClawHub (clawhub.ai) requires valid YAML frontmatter, proper metadata schema, and following strict field allowlists.

The recommended approach is to enhance the existing feedship SKILL.md files to fix critical YAML parsing issues and missing documentation, then publish using the Anthropic SDK or clawhub CLI. The main risks are YAML parsing failures from unquoted special characters (pipes and colons) and non-standard frontmatter fields that fail validation. Both issues are easily preventable with proper quoting and field management.

## Key Findings

### Recommended Stack

The SKILL.md format (v1.0) with YAML frontmatter (v1.1+) is the required skill definition format. The Anthropic SDK (beta) provides the official API for programmatic publishing to ClawHub. The `uv` tool is the recommended package installer for Python-based skills. Publishing can be done via Anthropic SDK, clawhub CLI, or manual web interface at clawhub.ai.

**Core technologies:**
- **SKILL.md (1.0)** — Required skill definition format with YAML frontmatter
- **YAML frontmatter (1.1+)** — Strict field allowlist: `name`, `description`, `license`, `allowed-tools`, `metadata`
- **Anthropic SDK (beta)** — Official API for programmatic clawhub publishing
- **uv** — Recommended Python package installer for skills

### Expected Features

**Must have (table stakes):**
- YAML frontmatter with `name` and `description` — ClawHub parses for indexing and activation
- Installation instructions — Users need install commands (uv/pipx)
- Complete command reference — All subcommands documented
- Options for each command — Customization flags explained
- Examples for common commands — Copy-paste usability

**Should have (competitive):**
- `--json` output flag documentation — Machine-readable output for scripting
- `info` command documentation — Diagnostic functionality (added in v1.5)
- Output format documentation — Rich tables/panels description
- Common workflow patterns — Initial setup, daily workflow, management
- Platform caveats — China/restricted network guidance
- Cron trigger documentation — Scheduled automation support

**Defer (v2+):**
- Video walkthrough linked in SKILL.md
- Interactive examples
- Multi-language SKILL variants (SKILL.zh-CN.md)

### Architecture Approach

Skills follow a discovery-and-invocation pattern: agents match user input against skill `description` fields, then read SKILL.md and execute documented CLI commands. Skills are published to ClawHub registry (clawhub.ai) and installed to `~/.openclaw/skills/` or project `skills/` directories. The skill folder structure is minimal: `SKILL.md` required, `references/` optional, `.clawhub/` for origin tracking.

**Major components:**
1. **SKILL.md** — Required skill definition with YAML frontmatter and markdown documentation
2. **Metadata schema** — Declares `requires.bins`, `requires.env`, `cron` triggers in `metadata.openclaw`
3. **ClawHub registry** — clawhub.ai hosts published skills with API at `/api/v1/skills/{slug}`

### Critical Pitfalls

1. **YAML parsing failure from pipe characters** — Command syntax like `feed add|list|remove` uses `|` which YAML interprets as block scalar indicator. Must quote: `'feed add|list|remove'`

2. **YAML parsing failure from unquoted colons** — Description text like `3-section digest: (A)` has colons that YAML interprets as mapping keys. Must quote or escape.

3. **Non-standard `compatibility` field** — Validation rejects fields outside allowlist (`name`, `description`, `license`, `allowed-tools`, `metadata`). Remove from frontmatter, move to body.

4. **Metadata format incompatibility** — Different skills use inconsistent metadata schemas (`clawdbot` vs `openclaw`). Must verify correct format against published reference skills.

5. **Skill name validation** — Names must match `^[a-z0-9-]+$` pattern (lowercase, hyphens only, max 64 chars).

## Implications for Roadmap

Based on research, the primary deliverable is fixing and publishing existing skills. The work is a single focused phase rather than multiple phases.

### Phase 1: Skill Enhancement and Publishing

**Rationale:** The existing SKILL.md files have critical YAML parsing issues that must be fixed before any publishing attempt. Both feedship and ai-daily skills need the same fixes applied.

**Delivers:**
- feedship SKILL.md with fixed YAML (quoted pipes/colons, removed compatibility field)
- feedship SKILL.md with `info` command documentation (INFO-01 through INFO-07)
- feedship SKILL.md with `--json` flag documented
- feedship SKILL.md version updated to 1.5
- ai-daily SKILL.md with `feedship info --json` diagnostic tip
- Both skills validated via `package_skill.py`

**Uses:** Stack elements from STACK.md (YAML frontmatter, Anthropic SDK for publishing)

**Implements:** Architecture patterns from ARCHITECTURE.md (skill folder structure, metadata schema)

**Avoids:** All 5 critical pitfalls from PITFALLS.md

### Phase Ordering Rationale

- **Skill Enhancement must come first** — Cannot publish with broken YAML parsing or non-standard frontmatter fields
- **feedship skill is primary** — ai-daily depends on feedship (mentioned as dependency), so feedship publishes first
- **Documentation completeness after parsing fixes** — Once YAML is valid, add missing `info` command and `--json` flag docs
- **Validation is the gate** — `package_skill.py` must pass before attempting publish

### Research Flags

Phases with standard patterns (skip research-phase):
- **Skill enhancement:** Well-documented format with clear validation scripts (quick_validate.py, package_skill.py)
- **SKILL.md documentation:** Clear template from existing skills

Phases needing deeper research during planning:
- **ClawHub publishing verification:** Web search for clawhub.ai returned errors; cannot confirm API endpoints or publish flow. May need direct verification at clawhub.ai

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Based on official SKILL.md format documentation and verified existing skill files |
| Features | MEDIUM | Based on existing skills and community patterns; clawhub.ai was unreachable for direct verification |
| Architecture | HIGH | Official ClawHub documentation on GitHub; verified skill structures |
| Pitfalls | HIGH | Based on actual validation scripts (package_skill.py, quick_validate.py) and error messages |

**Overall confidence:** MEDIUM

The main uncertainty is whether clawhub.ai is accessible and whether the publishing API works as documented. Direct verification during the enhancement phase is recommended.

### Gaps to Address

- **ClawHub API accessibility:** Unable to search clawhub.ai during research. Verify API endpoints and publishing flow during Phase 1.
- **Metadata schema final confirmation:** While the architecture docs specify `metadata.openclaw`, the `clawdbot` format exists in some skills. Verify correct format by examining a published skill after first publish.

## Sources

### Primary (HIGH confidence)
- OpenClaw skill-creator skill: `/Users/y3/clawd/skills/skill-creator/SKILL.md` — official validation scripts
- Quick validation script: `/Users/y3/clawd/skills/skill-creator/scripts/quick_validate.py` — YAML parsing rules
- Package script: `/Users/y3/clawd/skills/skill-creator/scripts/package_skill.py` — validation allowlist
- ClawHub Architecture Documentation — official GitHub docs

### Secondary (HIGH confidence)
- Existing feedship skills: `/Users/y3/feedship/skills/feedship/SKILL.md`, `/Users/y3/feedship/skills/ai-daily/SKILL.md`
- Reference published skills: `/Users/y3/clawd/skills/summarize/SKILL.md`, `/Users/y3/clawd/skills/skill-vetter/SKILL.md`
- Anthropic SDK `skills.d.ts` — API types for beta skills API

### Tertiary (MEDIUM confidence)
- Community skill collection: VoltAgent/awesome-openclaw-skills — for competitive feature analysis
- Project STATE.md requirements — for understanding v1.6 milestone context

---
*Research completed: 2026-04-03*
*Ready for roadmap: yes*
