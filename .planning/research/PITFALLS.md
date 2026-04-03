# Pitfalls Research: OpenClaw Skill Publishing

**Domain:** Publishing Claude Code skills to ClawHub
**Researched:** 2026-04-03
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: YAML Parsing Failure from Pipe Characters in Description

**What goes wrong:**
SKILL.md fails to parse during validation. The `package_skill.py` script exits with error "Invalid YAML in frontmatter".

**Why it happens:**
The pipe character `|` in command references like `feed add|list|remove` is interpreted by YAML as a block scalar indicator. YAML then expects indented content following the `|`, but finds plain text instead, causing parse failure.

Example from current feedship SKILL.md:
```yaml
description: ...Commands: feed add|list|remove, fetch, article list|view|open|related, search, discover.
```

**How to avoid:**
Quote any description containing pipe characters that are part of command syntax:
```yaml
description: "...Commands: 'feed add|list|remove', 'fetch', 'article list|view|open|related'..."
```

**Warning signs:**
Validation fails with "mapping values are not allowed here" or "Invalid YAML in frontmatter"

**Phase to address:** Skill Enhancement Phase (before packaging)

---

### Pitfall 2: YAML Parsing Failure from Unquoted Colons in Description

**What goes wrong:**
Description containing colons followed by text on the same line causes YAML parse errors.

**Why it happens:**
A colon `:` in YAML starts a new mapping key. When the description contains text like `3-section digest: (A)` on the same logical line, YAML interprets the colon as syntax rather than literal text.

Example from current ai-daily SKILL.md:
```yaml
description: ...generates a 3-section digest: (A) Today's new articles with summaries...
```

**How to avoid:**
Quote any description containing colons that are not YAML syntax:
```yaml
description: "...generates a '3-section digest: (A)...'..."
```

**Warning signs:**
Same YAML parse errors as Pitfall 1.

**Phase to address:** Skill Enhancement Phase (before packaging)

---

### Pitfall 3: Non-Standard Frontmatter Fields Cause Validation Failure

**What goes wrong:**
`package_skill.py` validation rejects the SKILL.md due to unexpected frontmatter fields.

**Why it happens:**
The validation script enforces strict allowlist for frontmatter properties:

```python
ALLOWED_PROPERTIES = {'name', 'description', 'license', 'allowed-tools', 'metadata'}
```

The current feedship SKILL.md includes a `compatibility` field which is NOT in the allowlist:
```yaml
compatibility: Install with pipx (recommended): `pipx install 'feedship[cloudflare,ml]'` or uv: `uv pip install 'feedship[cloudflare,ml]'`
```

**How to avoid:**
1. Remove `compatibility` from frontmatter entirely
2. Move installation instructions into the SKILL.md body markdown section
3. Only use these frontmatter fields: `name`, `description`, `license`, `allowed-tools`, `metadata`

**Warning signs:**
Validation fails with "Unexpected key(s) in SKILL.md frontmatter: compatibility"

**Phase to address:** Skill Enhancement Phase (before packaging)

---

### Pitfall 4: Metadata Format Incompatibility with ClawHub

**What goes wrong:**
The `metadata.openclaw.requires.bins` format used in current skills may not be the correct format for ClawHub publishing.

**Why it happens:**
Different OpenClaw skills use inconsistent metadata formats:
- Summarize skill uses: `metadata: {"clawdbot":{"emoji":"...","requires":...}}}`
- Current feedship uses: `metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}`

This suggests the metadata schema may have changed or varies by use case.

**How to avoid:**
1. Review published skills in `~/clawd/skills/` for the correct metadata schema
2. Use the format from similar published skills (e.g., summarize, skill-creator)
3. Keep metadata minimal - only include what's strictly required for the skill to work

**Warning signs:**
Skill installs but `openclaw skills check` shows requirements as unmet

**Phase to address:** Skill Enhancement Phase (metadata verification sub-task)

---

### Pitfall 5: Skill Name Violates Naming Conventions

**What goes wrong:**
Validation rejects the skill name for not matching hyphen-case requirements.

**Why it happens:**
The validation script enforces:
- Lowercase letters, digits, and hyphens only
- Cannot start or end with hyphen
- Cannot contain consecutive hyphens
- Maximum 64 characters

**How to avoid:**
Ensure skill name matches pattern: `^[a-z0-9-]+$`

Valid examples: `feedship`, `ai-daily`, `skill-vetter`

**Warning signs:**
Validation fails with name-related error messages

**Phase to address:** Skill Enhancement Phase (should already be correct if following current naming)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Including `compatibility` field | Easier to see install info | Validation failure, non-standard | Never (remove it) |
| Detailed "Output Formats" section | Shows rich tables/panels | Bloats SKILL.md, violates conciseness principle | Never - this is Claude context waste |
| "Common Patterns" section | Nice examples | SKILL.md bloat, violates conciseness | Never - move to references/ or delete |
| China/restricted network notes | Helps some users | Extraneous for global distribution | Only if skill targets China specifically |

---

## Integration Gotchas

| Issue | What Goes Wrong | Correct Approach |
|-------|-----------------|------------------|
| Skill path outside workspace root | "Skipping skill path that resolves outside its configured root" | Skills must be under the configured skills root directory |
| uv dependency declared but not verified | Skill shows as "not ready" | Declare uv as required bin in metadata, verify with `openclaw skills check` |
| feedship CLI not installed | Skill triggers but commands fail | Document installation clearly in Setup section |
| Missing ML/cloudflare extras | Semantic search commands fail | Specify full extras in installation: `feedship[cloudflare,ml]` |

---

## "Looks Done But Isn't" Checklist

- [ ] **Frontmatter:** Only `name`, `description`, `license`, `allowed-tools`, `metadata` present - verify no `compatibility` field
- [ ] **Description:** No bare `|` or `:` characters that break YAML parsing - all special characters quoted
- [ ] **Validation:** `package_skill.py` runs without error (not just `quick_validate.py`)
- [ ] **Length:** SKILL.md body under 500 lines (progressive disclosure principle)
- [ ] **No extraneous files:** No README.md, INSTALLATION_GUIDE.md, or other aux files
- [ ] **Metadata schema:** Confirmed correct format by comparing to published skills
- [ ] **Skill name:** Verified hyphen-case, lowercase only, max 64 chars

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| YAML parse failure | LOW | Quote problematic characters in description |
| `compatibility` field rejection | LOW | Remove field from frontmatter, move content to body |
| Metadata format wrong | MEDIUM | Compare with published skills, rewrite metadata |
| Skill path outside root | MEDIUM | Move skill directory under configured skills root |
| SKILL.md too long | LOW | Move detailed content to `references/` subdirectory |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| YAML parsing (pipe chars) | Skill Enhancement: Fix descriptions | Run `uv run --with pyyaml python quick_validate.py` until passes |
| YAML parsing (colon) | Skill Enhancement: Fix descriptions | Same validation test |
| Non-standard frontmatter | Skill Enhancement: Clean frontmatter | Package command succeeds |
| Metadata format | Skill Enhancement: Verify metadata | `openclaw skills check` shows skill ready |
| Naming convention | Initial naming (already correct) | Validation passes |

---

## Sources

- OpenClaw skill-creator skill: `/Users/y3/clawd/skills/skill-creator/SKILL.md`
- Quick validation script: `/Users/y3/clawd/skills/skill-creator/scripts/quick_validate.py`
- Package script: `/Users/y3/clawd/skills/skill-creator/scripts/package_skill.py`
- Reference published skills: `/Users/y3/clawd/skills/summarize/SKILL.md`, `/Users/y3/clawd/skills/skill-vetter/SKILL.md`
- Current feedship skill (with issues): `/Users/y3/feedship/skills/feedship/SKILL.md`
- Current ai-daily skill (with issues): `/Users/y3/feedship/skills/ai-daily/SKILL.md`

---
*Pitfalls research for: OpenClaw skill publishing*
*Researched: 2026-04-03*
