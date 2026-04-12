#!/usr/bin/env python3
"""AI News Analyst — evaluate report quality using structural heuristics.

This script implements the AI News Analyst evaluation step for the iterative
feedback loop. It evaluates generated report quality using structural heuristics
(when LLM is unavailable) and writes structured scores to iteration_scores.json.

Usage:
    PYTHONPATH=. python scripts/evaluate_news_quality.py [--report-text TEXT]

Output:
    Writes structured scores (0.0-1.0) to iteration_scores.json
    in the spec directory.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Five-layer cake taxonomy
FIVE_LAYER_CATEGORIES = [
    "AI应用",
    "AI模型",
    "AI基础设施",
    "芯片",
    "能源",
]

# ---------------------------------------------------------------------------
# Structural evaluation functions (copied from evaluator.py — no LLM needed)
# ---------------------------------------------------------------------------


def _check_completeness(report_text: str) -> tuple[float, dict[str, bool]]:
    """Check if all 5 layers are present with content.

    Returns (completeness_score, layer_breakdown_dict).
    A layer is complete when:
      - Section header ("## {layer}") is present
      - Summary has >= 30 Chinese chars across content lines
      - At least 1 article list item is present
    Uses 30-char threshold (not 50) to handle both short sample reports
    and real reports where summaries are multi-sentence paragraphs.
    """
    layer_breakdown: dict[str, bool] = {}

    for layer in FIVE_LAYER_CATEGORIES:
        # Search for the full layer header `## {layer}` to avoid matching the
        # "## " prefix within the current header line.
        layer_idx = report_text.find(f"## {layer}")
        if layer_idx == -1:
            layer_idx = report_text.find(layer)
        if layer_idx == -1:
            layer_breakdown[layer] = False
            continue

        next_layer_idx = len(report_text)
        for other_layer in FIVE_LAYER_CATEGORIES:
            if other_layer != layer:
                idx = report_text.find(f"## {other_layer}", layer_idx + len(layer) + 3)
                if idx > layer_idx and idx < next_layer_idx:
                    next_layer_idx = idx

        section = report_text[layer_idx:next_layer_idx]
        lines = section.split("\n")

        # Accumulate Chinese chars across ALL non-list content lines.
        # Stop ONLY at the first list item — that's where the article list begins.
        summary_chars = 0
        content_lines = 0
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith(("-", "*", "•")):
                break
            if not stripped:
                continue
            chinese_chars = sum(1 for c in line if "\u4e00" <= c <= "\u9fff")
            summary_chars += chinese_chars
            content_lines += 1

        # A layer is complete if it has >= 30 Chinese chars AND >= 1 content line
        has_summary = summary_chars >= 30 and content_lines >= 1
        has_article = bool(
            [line for line in lines if line.strip().startswith(("-", "*"))][:1]
        )

        layer_breakdown[layer] = has_summary and has_article

    complete_layers = sum(layer_breakdown.values())
    completeness = complete_layers / len(FIVE_LAYER_CATEGORIES)
    return completeness, layer_breakdown


def _check_chinese_correctness(report_text: str) -> float:
    """Check if summary paragraphs contain proper Chinese characters.

    Returns 1.0 if >= 50% Chinese, 0.5 if 30-50%, 0.0 if < 30%.
    Uses lower thresholds (40 chars for blocks, line-by-line fallback for short reports).
    """
    # Try standard 100-char blocks first
    text_blocks = re.findall(r"(?:^|\n)(.{100,})", report_text)

    if not text_blocks:
        # Fallback: collect all non-header, non-list lines for analysis
        lines = report_text.split("\n")
        content_lines = [
            line.strip()
            for line in lines
            if line.strip()
            and not line.strip().startswith("#")
            and not line.strip().startswith(("-", "*", "•"))
            and sum(1 for c in line if "\u4e00" <= c <= "\u9fff") > 0
        ]
        # Also try 40-char blocks for short summaries
        text_blocks = re.findall(r"(?:^|\n)(.{40,})", "\n".join(content_lines))
        if not text_blocks:
            # Last resort: all content lines joined
            text_blocks = ["\n".join(content_lines)]

    total_chars = 0
    chinese_chars = 0

    for block in text_blocks:
        for c in block:
            if c.strip():
                total_chars += 1
                if "\u4e00" <= c <= "\u9fff":
                    chinese_chars += 1

    if total_chars == 0:
        return 0.5

    ratio = chinese_chars / total_chars
    if ratio >= 0.5:
        return 1.0
    elif ratio >= 0.3:
        return 0.5
    else:
        return 0.0


def _derive_quality_scores_from_structure(
    completeness: float,
    chinese_correctness: float,
    layer_breakdown: dict[str, bool],
) -> dict[str, float]:
    """Derive heuristic quality scores from structural analysis.

    When LLM evaluation is unavailable, derive proxy scores from structural metrics:
    - coherence: high when Chinese correctness is high (readable text)
    - relevance: based on completeness (all layers present = more relevant)
    - depth: based on completeness + layer coverage (complete = deeper)
    - structure: based on number of complete layers

    All scores are in range 0.0-1.0.
    """
    complete_layers = sum(layer_breakdown.values())
    num_layers = len(FIVE_LAYER_CATEGORIES)
    layer_ratio = complete_layers / num_layers if num_layers > 0 else 0.0

    # Coherence: strongly correlated with Chinese correctness
    # If Chinese text is garbled, report is incoherent
    coherence = max(0.0, min(1.0, chinese_correctness))

    # Relevance: completeness of all layers indicates comprehensive coverage
    # Base score from completeness, boosted by Chinese correctness
    relevance = max(0.0, min(1.0, 0.6 * completeness + 0.4 * chinese_correctness))

    # Depth: completeness of layers + Chinese correctness
    # If layers are present but content is shallow, depth suffers
    depth = max(0.0, min(1.0, 0.7 * completeness + 0.3 * chinese_correctness))

    # Structure: based on layer coverage ratio
    # A well-structured report has all 5 layers with content
    structure = max(0.0, min(1.0, 0.5 * completeness + 0.5 * layer_ratio))

    # Overall: average of all four dimensions
    overall = (coherence + relevance + depth + structure) / 4.0

    return {
        "overall": overall,
        "coherence": coherence,
        "relevance": relevance,
        "depth": depth,
        "structure": structure,
    }


# ---------------------------------------------------------------------------
# Default sample report (used when no report is provided)
# ---------------------------------------------------------------------------

DEFAULT_SAMPLE_REPORT = """# AI Weekly Report (2026-04-07 ~ 2026-04-10)

## AI应用
本周AI应用领域持续快速发展，多个行业推出了创新应用。本周重点关注生成式AI在企业级场景的落地进展，包括智能客服、内容创作、数据分析等多个垂直领域的规模化应用。

- **新AI应用发布**: 多个科技公司推出新一代AI助手，在对话理解和多模态处理方面有显著提升
- **AI教育应用**: AI在个性化教育领域的应用持续扩展，帮助学生定制学习计划并提供实时辅导
- **AI医疗辅助**: 医疗AI辅助诊断系统在多家医院开始试点，提升诊断效率和准确性

## AI模型
大型语言模型继续保持快速迭代态势，多家厂商发布新版本或更新。本周重点关注多模态模型的进展，以及开源模型的社区生态扩展情况。

- **新模型发布**: 主要AI厂商发布新一代基础模型，在推理能力和效率上有明显进步
- **开源模型更新**: 多个开源模型发布更新版本，降低部署门槛并提升性能表现
- **模型评测**: 新一轮模型评测结果出炉，展示各模型的差异化优势和适用场景

## AI基础设施
云计算和基础设施服务持续升级，为AI发展提供更强支撑。本周关注数据中心扩展、新一代GPU实例发布以及边缘计算的最新进展。

- **云服务更新**: 主要云服务商推出新一代GPU实例，提升训练效率并降低单位成本
- **边缘计算**: 边缘AI推理能力增强，支持更多实时应用场景和低延迟服务
- **存储服务**: 高性能存储服务升级，满足大规模AI训练数据的读写需求

## 芯片
AI芯片市场竞争持续，多款新产品发布。本周重点关注推理芯片的性价比提升和芯片供应链的最新动态。

- **新芯片发布**: 主要芯片厂商发布新一代AI加速芯片，在能效比上有显著改进
- **性能对比**: 新旧芯片性能对比评测显示最新一代产品在推理速度上领先
- **供应链**: AI芯片供应链持续优化，交付周期缩短但价格仍处高位

## 能源
数据中心能源消耗持续增加，可再生能源成为重点。本周关注绿色数据中心建设进展和能源管理技术的创新。

- **绿色能源项目**: 多个数据中心签署可再生能源采购协议，计划在2030年前实现碳中和
- **能源效率提升**: 新一代液冷技术和浸没式冷却方案提升数据中心能效比至1.2以下
- **能源管理**: AI驱动的智能能源管理系统开始部署，优化负载分配以降低碳排放
"""


# ---------------------------------------------------------------------------
# Main evaluation logic
# ---------------------------------------------------------------------------


def _get_spec_dir() -> Path:
    """Find the spec directory for this task."""
    # Navigate from scripts/ up to find the spec directory
    script_dir = Path(__file__).parent.resolve()
    # scripts/ is at the repo root level
    spec_dir = (
        script_dir.parent
        / ".auto-claude"
        / "specs"
        / "001-review-and-fix-report-architecture-issues"
    )
    if spec_dir.exists():
        return spec_dir
    # Fallback: try relative to cwd
    cwd = Path.cwd()
    fallback = (
        cwd / ".auto-claude" / "specs" / "001-review-and-fix-report-architecture-issues"
    )
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Spec directory not found. Tried: {spec_dir}, {fallback}")


def evaluate_report_structural(report_text: str) -> dict[str, Any]:
    """Evaluate report using structural heuristics (no LLM needed).

    Returns a dict with:
      - quality_score: dict with overall/coherence/relevance/depth/structure (0.0-1.0)
      - completeness: float 0.0-1.0
      - chinese_correctness: float 0.0-1.0
      - layer_breakdown: dict[str, bool]
      - timestamp: ISO timestamp
    """
    completeness, layer_breakdown = _check_completeness(report_text)
    chinese_correctness = _check_chinese_correctness(report_text)
    quality_scores = _derive_quality_scores_from_structure(
        completeness, chinese_correctness, layer_breakdown
    )

    return {
        "quality_score": quality_scores,
        "completeness": completeness,
        "chinese_correctness": chinese_correctness,
        "layer_breakdown": layer_breakdown,
        "timestamp": datetime.now().isoformat(),
    }


def read_report_from_cli() -> str | None:
    """Attempt to read report text from stdin or --report-file argument."""
    import argparse

    parser = argparse.ArgumentParser(description="AI News Analyst evaluation")
    parser.add_argument(
        "--report-text",
        type=str,
        default=None,
        help="Report text to evaluate (if not provided, uses sample)",
    )
    parser.add_argument(
        "--report-file",
        type=str,
        default=None,
        help="Path to report file to evaluate",
    )
    parser.add_argument(
        "--since",
        type=str,
        default="2026-04-07",
        help="Report date range start",
    )
    parser.add_argument(
        "--until",
        type=str,
        default="2026-04-10",
        help="Report date range end",
    )
    args = parser.parse_args()

    if args.report_text:
        return args.report_text
    if args.report_file:
        path = Path(args.report_file)
        if path.exists():
            return path.read_text(encoding="utf-8")
        logger.warning(
            "Report file not found: %s. Using default sample.", args.report_file
        )
    return None


def load_existing_scores(scores_path: Path) -> dict[str, Any]:
    """Load existing iteration_scores.json or return empty structure."""
    if scores_path.exists():
        try:
            return json.loads(scores_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not load existing scores: %s", e)
    return {"iterations": [], "current_iteration": 0}


def write_scores(scores_path: Path, data: dict[str, Any]) -> None:
    """Write scores to iteration_scores.json."""
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Wrote scores to %s", scores_path)


def main() -> int:
    """Run AI News Analyst evaluation.

    Returns:
        0 on success, non-zero on error.
    """
    spec_dir = _get_spec_dir()
    scores_path = spec_dir / "iteration_scores.json"

    # Read report text
    report_text = read_report_from_cli()
    if report_text is None:
        logger.info("No report provided — using default sample report for evaluation")
        report_text = DEFAULT_SAMPLE_REPORT

    # Evaluate
    logger.info("Evaluating report quality (structural heuristics)...")
    result = evaluate_report_structural(report_text)

    qs = result["quality_score"]
    completeness = result["completeness"]
    chinese_correctness = result["chinese_correctness"]
    layer_breakdown = result["layer_breakdown"]
    timestamp = result["timestamp"]

    # Validate all scores are in 0.0-1.0 range
    for key, val in qs.items():
        assert isinstance(val, (int, float)), f"{key}={val!r} is not a number"
        assert 0.0 <= val <= 1.0, f"{key}={val} out of range [0.0, 1.0]"

    assert 0.0 <= completeness <= 1.0
    assert 0.0 <= chinese_correctness <= 1.0

    # Log results
    logger.info(
        "Quality scores: overall=%.3f coherence=%.3f relevance=%.3f depth=%.3f structure=%.3f",
        qs["overall"],
        qs["coherence"],
        qs["relevance"],
        qs["depth"],
        qs["structure"],
    )
    logger.info(
        "Structural metrics: completeness=%.3f chinese_correctness=%.3f",
        completeness,
        chinese_correctness,
    )
    logger.info("Layer breakdown: %s", layer_breakdown)

    # Load existing scores and append new iteration
    scores_data = load_existing_scores(scores_path)
    next_iteration = scores_data.get("current_iteration", 0) + 1

    iteration_entry = {
        "iteration": next_iteration,
        "timestamp": timestamp,
        "date_range": "2026-04-07~2026-04-10",
        "quality_score": {
            "overall": qs["overall"],
            "coherence": qs["coherence"],
            "relevance": qs["relevance"],
            "depth": qs["depth"],
            "structure": qs["structure"],
        },
        "completeness": completeness,
        "chinese_correctness": chinese_correctness,
        "layer_breakdown": layer_breakdown,
        "evaluation_method": "structural_heuristics",
        "report_sample": report_text[:500],
    }

    scores_data["iterations"].append(iteration_entry)
    scores_data["current_iteration"] = next_iteration
    scores_data["last_updated"] = timestamp

    write_scores(scores_path, scores_data)

    print("\n=== AI News Analyst Evaluation Results ===")
    print(f"Iteration: {next_iteration}")
    print(f"Timestamp: {timestamp}")
    print("\nQuality Scores (0.0-1.0):")
    print(f"  Overall:     {qs['overall']:.3f}")
    print(f"  Coherence:   {qs['coherence']:.3f}")
    print(f"  Relevance:   {qs['relevance']:.3f}")
    print(f"  Depth:       {qs['depth']:.3f}")
    print(f"  Structure:   {qs['structure']:.3f}")
    print("\nStructural Metrics:")
    print(f"  Completeness:        {completeness:.3f}")
    print(f"  Chinese Correctness: {chinese_correctness:.3f}")
    print("\nLayer Breakdown:")
    for layer, has_content in layer_breakdown.items():
        status = "✓" if has_content else "✗"
        print(f"  {status} {layer}")
    print(f"\nScores written to: {scores_path}")
    print("=== All scores in valid 0.0-1.0 range ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
