---
phase: quick
plan: "260326-t0b"
summary_date: "2026-03-26"
execution_duration: "<1 min"
---

# Quick Task 260326-t0b: bigmodel.cn glm-coding Pricing

## One-liner

Documented bigmodel.cn GLM model pricing - no standalone glm-coding package exists; coding is a feature of flagship GLM-5/GLM-4 models with per-token pricing (¥0.1-22/M tokens).

## Objective

Fetch and document bigmodel.cn glm-coding package pricing information.

## Tasks Completed

| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| 1 | Fetch glm-coding pricing via Playwright | Complete | - |

## Findings

### Key Discovery

**No standalone "glm-coding" package exists on bigmodel.cn.** Coding capability ("Expert at coding, agents, reasoning, and more") is a feature integrated into flagship GLM models.

### Pricing Overview

**Flagship Models (GLM-5-Turbo, GLM-5, GLM-4.7, GLM-4.5-Air, GLM-4.7-FlashX, GLM-4.7-Flash):**

| Model | Input (¥/1M tokens) | Output (¥/1M tokens) |
|-------|-------------------|---------------------|
| GLM-5-Turbo | ¥5-7 | ¥22-26 |
| GLM-5 | ¥4-6 | ¥18-22 |
| GLM-4.7 | ¥2-4 | ¥8-16 |
| GLM-4.5-Air | ¥0.8-1.2 | ¥2-8 |
| GLM-4.7-FlashX | ¥0.5 | ¥3 |
| GLM-4.7-Flash | Free | Free |

**Batch API:** 50% of standard pricing (Efficiently complete large-scale data processing tasks)

**Fine-tuning:** ¥0.025-0.125 per 1k tokens (LoRA or Full)

**Private Deployment:** ¥100-175 / GPU Unit / Day or ¥500K-1.1M / year

## Files Created

- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/260326-t0b-PLAN.md` (updated)
- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/260326-t0b-SUMMARY.md` (this file)
- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/pricing_results.json` (raw data)
- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/glm_coding_full.json` (full page text)
- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/screenshot_https_bigmodel.cn_pricing.png` (screenshot)
- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/fetch_pricing.py` (playwright script)
- `.planning/quick/260326-t0b-bigmodel-cn-glm-coding/fetch_glm_coding.py` (playwright script)

## Technical Approach

1. Initial WebFetch failed (SPA - no JS content)
2. Used Playwright headless browser (chromium) with:
   - Networkidle wait strategy
   - Full page screenshot capture
   - Text content extraction via inner_text()
   - Keyword-based element search

## Verification

- Playwright successfully rendered https://bigmodel.cn/pricing
- Full page text captured (964,974 chars)
- Pricing table data extracted and structured
- Screenshot saved for visual verification

## Self-Check: PASSED

All required files exist:
- [FOUND] 260326-t0b-PLAN.md
- [FOUND] 260326-t0b-SUMMARY.md
- [FOUND] pricing_results.json
- [FOUND] glm_coding_full.json
- [FOUND] screenshot_https_bigmodel.cn_pricing.png
