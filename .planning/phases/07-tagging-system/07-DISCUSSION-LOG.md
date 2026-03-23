# Phase 7: Tagging System - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 07-tagging-system
**Areas discussed:** Tag management, Article tagging, Keyword matching, AI clustering, Tag filtering, Display format

---

## Tag Management

| Option | Description | Selected |
|--------|-------------|----------|
| CLI commands | `tag add`, `tag list`, `tag remove` | ✓ |

## Article Tagging Methods

| Option | Description | Selected |
|--------|-------------|----------|
| Manual only | `article tag <id> <tag>` | |
| Auto: keyword matching | Rule-based matching | ✓ |
| Auto: AI clustering | Embedding + clustering | ✓ |
| Keyword + AI clustering | Both approaches | ✓ |

## Keyword Matching Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Config file only | `~/.radar/tag-rules.yaml` | |
| CLI management | Commands to add/remove/list rules | ✓ |
| Natural language | Describe rules in plain text | |
| Config + CLI + regex | All three approaches | ✓ |

## Rule Conflict Handling

| Option | Description | Selected |
|--------|-------------|----------|
| First match only | Stop at first matching tag | |
| Multiple tags | Apply ALL matching tags | ✓ |

## AI Clustering Result Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Suggest only | Show suggestions for user to confirm | |
| Auto-generate | Directly create tags, user can delete | ✓ |
| Show only | Display clusters without creating tags | |

## AI Clustering Technology

| Option | Description | Selected |
|--------|-------------|----------|
| Full embedding | sentence-transformers + sqlite-vec | ✓ |
| Lightweight | YAKE/KeyBERT keyword extraction | |
| API-based | OpenAI/Anthropic (conflicts with no-API constraint) | |

## Tag Filtering Logic

| Option | Description | Selected |
|--------|-------------|----------|
| `--tag` single | Must have the tag | ✓ |
| `--tags a,b` OR | Has a OR has b | ✓ |
| AND logic needed | Both tags required | |

## Display Format

| Option | Description | Selected |
|--------|-------------|----------|
| Inline brackets | `[AI][News] Article Title` | ✓ |
| Separate column | Tags in dedicated column | |
| Color dots | Colored indicators | |

---

## User's Choices

- **Tag management:** CLI commands (`tag add/list/remove`)
- **Auto tagging:** Keyword matching + AI clustering
- **Rule config:** YAML file + CLI management + regex support
- **Rule conflict:** Apply all matching tags
- **AI clustering:** Auto-generate tags, user can delete
- **AI tech:** sentence-transformers + sqlite-vec
- **Filtering:** `--tag` single, `--tags a,b` OR logic
- **Display:** Inline brackets

## Deferred Ideas

None

