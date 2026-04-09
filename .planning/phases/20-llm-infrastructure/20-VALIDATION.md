---
phase: 20
slug: llm-infrastructure
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-08
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|---------|-------|
| **Framework** | pytest |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `uv run python -m pytest tests/test_llm.py -v` |
| **Full suite command** | `uv run python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-05-01 | 20-PLAN.md | 1 | test_llm_config_parsing | — | N/A | unit | `uv run python -m pytest tests/test_llm.py::TestLLMConfigParsing -v` | ✅ | ✅ green |
| 20-05-02 | 20-PLAN.md | 1 | test_provider_fallback_chain | — | N/A | unit | `uv run python -m pytest tests/test_llm.py::TestProviderFallbackChain -v` | ✅ | ✅ green |
| 20-05-03 | 20-PLAN.md | 1 | test_truncate_content | — | N/A | unit | `uv run python -m pytest tests/test_llm.py::TestTruncateContent -v` | ✅ | ✅ green |
| 20-05-04 | 20-PLAN.md | 1 | test_weight_gating | — | N/A | unit | `uv run python -m pytest tests/test_llm.py::TestWeightGating -v` | ✅ | ⚠️ skipped |
| 20-05-05 | 20-PLAN.md | 1 | test_concurrency_limit | — | N/A | unit | `uv run python -m pytest tests/test_llm.py::TestConcurrencyLimit -v` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ skipped*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---------|-------------|------------|-----------------|
| LLM provider fallback actually falls back | INFRA-01 | Requires mock server | Manual: set invalid provider, verify fallback |
| End-to-end LLM call | INFRA-01 | Requires live API or Ollama | Manual: `uv run feedship summarize --id <id>` confirmed via quick task 260408-1rz |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-08
