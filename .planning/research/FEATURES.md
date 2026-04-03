# Feature Research

**Domain:** OpenClaw Skill Publishing for feedship CLI
**Researched:** 2026-04-03
**Confidence:** MEDIUM

*Note: Web search for clawhub.ai returned errors. Analysis based on existing skill patterns in `/Users/y3/feedship/skills/`, OpenClaw metadata YAML frontmatter observed in existing SKILL.md files, and project requirements from `.planning/STATE.md`.*

## Feature Landscape

### Table Stakes (Required for clawhub Publishing)

These are non-negotiable for a publishable skill. Missing these = skill feels incomplete or unusable.

| Feature | Why Expected | Complexity | Status in feedship | Notes |
|---------|--------------|------------|-------------------|-------|
| YAML frontmatter with `name`, `description` | Clawhub parses this for skill index and activation | LOW | Present | Must include trigger phrases in description |
| Installation instructions | Users must know how to install | LOW | Present | Both `uv` and `pipx` recommended |
| Command reference (all subcommands) | Users need complete API documentation | MEDIUM | PARTIAL | Missing `info` command |
| Options for each command | Users need to customize behavior | MEDIUM | Present | feed, fetch, article, search, discover all have options |
| Examples for common commands | Copy-paste usability | MEDIUM | Present | Good examples in feedship, minimal in ai-daily |
| Compatibility/install requirements | Version constraints and dependencies | LOW | Present | `[cloudflare,ml]` extra documented |

### Differentiators (What Makes Skill Stand Out)

Features that elevate a skill from "functional" to "delightful." Not required, but valuable for clawhub discoverability.

| Feature | Value Proposition | Complexity | Status | Notes |
|---------|-------------------|------------|--------|-------|
| Output format documentation | Users know exactly what to expect | LOW | Present | Rich tables, panels, progress bars documented |
| Common workflow patterns | "How do I do X?" answered inline | MEDIUM | Present | Initial setup, daily workflow, feed management |
| Anti-patterns / gotchas | Prevents frustration | LOW | Partial | Network mirrors mentioned, but no general "avoid X" |
| Tips and edge case handling | "What if no articles today?" | LOW | Partial | ai-daily has good tips |
| --json output flag | Machine-readable output for scripting | LOW | MISSING | Not documented in SKILL.md |
| `info` command documentation | Diagnostic and introspection | LOW | MISSING | Added in v1.5 but not in SKILL.md |
| Cron trigger documentation | Scheduled automation | LOW | Present | ai-daily documents cron syntax |
| Platform/network caveats | China/restricted network guidance | MEDIUM | Present | Valuable differentiator |
| Rich output samples | Visual proof of quality | MEDIUM | Partial | ai-daily has complete example output |

### Anti-Features (Avoid These)

Features that seem valuable but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Documenting every CLI flag exhaustively | Completeness | Makes SKILL.md unreadable | Link to `feedship --help` for full reference |
| Including internal implementation details | Transparency | Users don't care, adds noise | Keep SKILL.md user-focused |
| Multiple skill formats | Flexibility | Fragmentation, harder to maintain | One SKILL.md per skill, keep it lean |
| Version-numbered filenames (SKILL.md) | Version tracking | Clutter on releases | Use git tags, document version in frontmatter |

## Feature Dependencies

```
feedship SKILL.md Enhancement
    ├──requires──> info command documented
    │                    └──in SKILL.md──> Version field updated to v1.5
    │
    ├──requires──> --json flag documented
    │                    └──in article list, article view, search, feed list
    │
    └──enhances──> clawhub publish readiness

ai-daily SKILL.md Enhancement
    ├──requires──> feedship skill (listed as dependency)
    │
    └──enhances──> Scheduled digest (cron trigger)
```

## Feature Gaps Analysis

### feedship SKILL.md

**Current state (v1.0):**
- Commands documented: feed (add/list/remove), fetch, article (list/view/open/related), search, discover
- Missing since v1.5 release:
  - `info` command with --version, --config, --storage, --json flags
  - `--json` output option for machine-readable results
- Version field still says "1.0" despite v1.5 info command release

**What to add:**
```markdown
### info

```bash
feedship info [options]
```

Display diagnostics: version, config, and storage information.

**Options:**
- `--version` — Show version only
- `--config` — Show config path and values
- `--storage` — Show storage path and stats
- `--json` — Output as JSON (machine-readable)

**Examples:**
```bash
feedship info                    # Show all info
feedship info --version         # Show version only
feedship info --config          # Show config path and values
feedship info --storage         # Show storage stats
feedship info --json            # JSON output for scripting
feedship info --config --json   # Config in JSON format
```
```

### ai-daily SKILL.md

**Current state:**
- Good report format with 3 sections (今日新文, 热点话题, 精选推荐)
- Workflow steps are clear but could be more prescriptive
- Missing: explicit handling of `--json` output from feedship commands

**What to enhance:**
- Add note about using `feedship info --json` for diagnostics
- Clarify that `feedship article list` can use `--json` for machine parsing

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Document `info` command in feedship SKILL.md | HIGH | LOW | P1 |
| Document `--json` flag in feedship SKILL.md | HIGH | LOW | P1 |
| Update version in feedship SKILL.md to v1.5 | LOW | LOW | P2 |
| Add `--json` examples to ai-daily skill | MEDIUM | LOW | P2 |
| Add complete example output to ai-daily SKILL.md | MEDIUM | LOW | P2 |
| Document info command options in ai-daily tips | LOW | LOW | P3 |

## Competitor Feature Analysis

*Note: Unable to search clawhub.ai directly. Analysis based on existing skill patterns.*

| Feature | Typical CLI Tool SKILL.md | feedship SKILL.md | Our Approach |
|---------|--------------------------|-------------------|--------------|
| YAML frontmatter | Yes, basic | Yes, with openclaw metadata | Keep existing |
| Installation section | Yes | Yes, with uv/pipx and mirrors | Keep, add upgrade sub-section |
| Command reference | Per-command | Per-command with subcommands | Extend with `info` |
| Options table | Sometimes | Inline with command | Keep inline |
| Examples | Minimal | Multiple per command | Keep |
| Output format docs | Rare | Present (Rich tables/panels) | Keep |
| Common patterns | Rare | Present (Initial, Daily, Management) | Keep |
| Tips/gotchas | Rare | Partial | Extend |
| JSON output | Rare | Missing | Add |
| Platform caveats | Rare | China network section | Keep |

## MVP Definition

### Launch With (v1.5.1 - Minimal Skill Update)

Minimum changes needed for clawhub publish readiness.

- [ ] Document `info` command in feedship SKILL.md — core diagnostic functionality users need
- [ ] Document `--json` flag across relevant commands — scripting and automation use cases
- [ ] Update feedship SKILL.md version from 1.0 to 1.5 — accurate representation

### Add After Validation (v1.5.x)

Enhancements after initial publish feedback.

- [ ] Add complete JSON output example in feedship SKILL.md
- [ ] Add diagnostic tip to ai-daily about `feedship info --json`
- [ ] Consider adding troubleshooting section for common errors

### Future Consideration (v2.0)

Defer until PMF established.

- [ ] Video walkthrough linked in SKILL.md
- [ ] Interactive examples (copy-paste that auto-detects user's feeds)
- [ ] Multi-language SKILL variants (SKILL.zh-CN.md)

## Sources

- Existing skills in `/Users/y3/feedship/skills/feedship/SKILL.md`
- Existing skills in `/Users/y3/feedship/skills/ai-daily/SKILL.md`
- Project requirements from `.planning/STATE.md` (v1.6 milestone)
- CLI implementation in `src/cli/` (info.py, article.py, feed.py, etc.)
- Template from `/Users/y3/.claude/get-shit-done/templates/research-project/FEATURES.md`

---
*Feature research for: OpenClaw Skill Publishing - feedship*
*Researched: 2026-04-03*
