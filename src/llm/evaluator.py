"""Quality evaluation and improvement loop for report generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

IMPROVEMENT_LOG_DIR = Path("~/.config/feedship/improvement_logs").expanduser()


@dataclass
class QualityScore:
    overall: float  # 0.0-1.0
    coherence: float
    relevance: float
    depth: float
    structure: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# Five-layer cake categories (must match report.py)
FIVE_LAYER_CATEGORIES = [
    "AI应用",
    "AI模型",
    "AI基础设施",
    "芯片",
    "能源",
]


@dataclass
class EnhancedQualityMetrics:
    """Enhanced quality metrics with completeness and Chinese correctness checks."""

    quality_score: QualityScore
    completeness: float  # 0.0-1.0, fraction of layers with full content
    chinese_correctness: float  # 0.0-1.0, fraction of Chinese characters in summaries
    layer_breakdown: dict[str, bool]  # layer -> has_complete_content
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ImprovementRecord:
    iteration: int
    date_range: str
    quality_score: QualityScore
    completeness: float
    chinese_correctness: float
    layer_breakdown: dict[str, bool]
    issues: list[str]
    prompt_adjustments: list[str]
    report_sample: str  # First 500 chars


async def evaluate_report(report_text: str) -> QualityScore:
    """Use LLM to evaluate report quality.

    Returns QualityScore with subscores for coherence, relevance, depth, structure.
    """
    from src.llm.chains import get_evaluate_chain

    chain = get_evaluate_chain()

    try:
        result = await chain.ainvoke({"report": report_text[:2000]})
        # Try to parse as JSON
        scores = json.loads(result)
        return QualityScore(
            overall=sum(scores.values()) / (4 * 100),
            coherence=scores.get("coherence", 0) / 100,
            relevance=scores.get("relevance", 0) / 100,
            depth=scores.get("depth", 0) / 100,
            structure=scores.get("structure", 0) / 100,
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
        logger.warning(
            "Quality evaluation failed to parse result: %s. Raw result: %s",
            e,
            result[:500] if result else "empty",
        )
        # Fallback: try simple 0-1 score parsing from existing chain
        try:
            score_val = float(result.strip())
            return QualityScore(
                overall=score_val,
                coherence=score_val,
                relevance=score_val,
                depth=score_val,
                structure=score_val,
            )
        except ValueError:
            logger.warning(
                "Quality evaluation completely failed, returning default 0.5"
            )
            return QualityScore(
                overall=0.5, coherence=0.5, relevance=0.5, depth=0.5, structure=0.5
            )


def _check_completeness(report_text: str) -> tuple[float, dict[str, bool]]:
    """Check if all 5 layers are present with content.

    Returns (completeness_score, layer_breakdown_dict).
    Completeness = fraction of layers that have:
      - Section header present
      - Non-empty summary paragraph (>= 50 chars)
      - At least 1 article listed
    """
    layer_breakdown: dict[str, bool] = {}

    for layer in FIVE_LAYER_CATEGORIES:
        # Check if layer section exists
        if layer not in report_text:
            layer_breakdown[layer] = False
            continue

        # Find the section for this layer
        layer_idx = report_text.find(layer)
        # Find next layer or end of section
        next_layer_idx = len(report_text)
        for other_layer in FIVE_LAYER_CATEGORIES:
            if other_layer != layer:
                idx = report_text.find(other_layer, layer_idx + len(layer))
                if idx > layer_idx and idx < next_layer_idx:
                    next_layer_idx = idx

        section = report_text[layer_idx:next_layer_idx]

        # Check for summary paragraph (>= 50 chars of Chinese text after layer header)
        # The summary typically appears right after "### N. {Layer}" or after layer name
        lines = section.split("\n")
        summary_chars = 0
        for line in lines[1:]:  # Skip the layer header line itself
            # Count Chinese characters in this line
            chinese_chars = sum(1 for c in line if "\u4e00" <= c <= "\u9fff")
            summary_chars += chinese_chars
            if chinese_chars >= 20:  # Found a substantive Chinese text line
                break

        has_summary = summary_chars >= 50

        # Check for at least 1 article (list items with - or *)
        has_article = bool(
            [line for line in lines if line.strip().startswith(("-", "*"))][:1]
        )

        layer_breakdown[layer] = has_summary and has_article

    complete_layers = sum(layer_breakdown.values())
    completeness = complete_layers / len(FIVE_LAYER_CATEGORIES)
    return completeness, layer_breakdown


def _check_chinese_correctness(report_text: str) -> float:
    """Check if summary paragraphs contain proper Chinese characters.

    Returns a score 0.0-1.0 representing fraction of Chinese characters.
    Scores 1.0 if >= 50% of characters are Chinese.
    Scores 0.5 if 30-50% are Chinese.
    Scores 0.0 if < 30% are Chinese (likely garbled/English).
    """
    import re

    # Extract paragraphs that look like summaries (between layer headers)
    # Look for substantial text blocks (>= 100 chars)
    text_blocks = re.findall(r"(?:^|\n)(.{100,})", report_text)

    if not text_blocks:
        return 0.5  # Default if no substantial text found

    total_chars = 0
    chinese_chars = 0

    for block in text_blocks:
        for c in block:
            if c.strip():  # Only count non-whitespace
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


async def evaluate_report_enhanced(report_text: str) -> EnhancedQualityMetrics:
    """Enhanced evaluation with completeness and Chinese correctness checks.

    Returns EnhancedQualityMetrics with quality score + completeness + Chinese correctness.
    """
    try:
        quality_score = await evaluate_report(report_text)
        completeness, layer_breakdown = _check_completeness(report_text)
        chinese_correctness = _check_chinese_correctness(report_text)

        return EnhancedQualityMetrics(
            quality_score=quality_score,
            completeness=completeness,
            chinese_correctness=chinese_correctness,
            layer_breakdown=layer_breakdown,
        )
    except Exception as e:
        logger.warning("Enhanced evaluation failed: %s. Returning defaults.", e)
        default_score = QualityScore(
            overall=0.5, coherence=0.5, relevance=0.5, depth=0.5, structure=0.5
        )
        return EnhancedQualityMetrics(
            quality_score=default_score,
            completeness=0.5,
            chinese_correctness=0.5,
            layer_breakdown=dict.fromkeys(FIVE_LAYER_CATEGORIES, False),
        )


def suggest_improvements(quality_score: QualityScore) -> list[str]:
    """Generate prompt adjustment suggestions based on quality subscores."""
    suggestions = []
    if quality_score.depth < 0.6:
        suggestions.append("Increase prompt weight for analysis and insights")
    if quality_score.relevance < 0.6:
        suggestions.append("Adjust relevance filtering threshold")
    if quality_score.structure < 0.6:
        suggestions.append("Improve template structure directives")
    if quality_score.coherence < 0.6:
        suggestions.append("Strengthen transition guidance in layer summaries")
    return suggestions


def log_improvement(record: ImprovementRecord) -> None:
    """Log improvement record to file (file-based approach from decision checkpoint)."""
    IMPROVEMENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = IMPROVEMENT_LOG_DIR / f"iteration_{record.iteration:04d}.json"
    with open(log_file, "w") as f:
        json.dump(
            {
                "iteration": record.iteration,
                "date_range": record.date_range,
                "quality_score": {
                    "overall": record.quality_score.overall,
                    "coherence": record.quality_score.coherence,
                    "relevance": record.quality_score.relevance,
                    "depth": record.quality_score.depth,
                    "structure": record.quality_score.structure,
                    "timestamp": record.quality_score.timestamp,
                },
                "completeness": record.completeness,
                "chinese_correctness": record.chinese_correctness,
                "layer_breakdown": record.layer_breakdown,
                "issues": record.issues,
                "prompt_adjustments": record.prompt_adjustments,
                "report_sample": record.report_sample,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info("Logged improvement iteration %d to %s", record.iteration, log_file)


def run_improvement_loop(
    since: str,
    until: str,
    iterations: int = 100,
    auto_summarize: bool = True,
) -> dict[str, Any]:
    """Run N automated improvement iterations on report quality.

    Each iteration:
    1. Generate report
    2. Evaluate quality (enhanced - includes completeness and Chinese correctness)
    3. Log results
    4. Apply incremental improvements for next iteration

    Returns summary dict with all iteration scores.
    """
    import asyncio

    from src.application.report import cluster_articles_for_report, render_report

    results = []
    for i in range(1, iterations + 1):
        # Generate report
        data = cluster_articles_for_report(
            since=since, until=until, limit=100, auto_summarize=auto_summarize
        )
        report_text = asyncio.run(render_report(data))

        # Evaluate quality (enhanced - includes completeness and Chinese correctness)
        enhanced = asyncio.run(evaluate_report_enhanced(report_text))
        score = enhanced.quality_score
        completeness = enhanced.completeness
        chinese_correctness = enhanced.chinese_correctness
        layer_breakdown = enhanced.layer_breakdown

        # Generate issues and adjustments
        issues = [
            f"{dim}={getattr(score, dim):.2f}"
            for dim in ["coherence", "relevance", "depth", "structure"]
            if getattr(score, dim) < 0.6
        ]
        # Add completeness issues
        if completeness < 1.0:
            missing_layers = [
                layer
                for layer, has_content in layer_breakdown.items()
                if not has_content
            ]
            issues.append(
                f"completeness={completeness:.2f} (missing: {missing_layers})"
            )
        # Add Chinese correctness issues
        if chinese_correctness < 1.0:
            issues.append(f"chinese_correctness={chinese_correctness:.2f}")
        adjustments = suggest_improvements(score)

        # Log
        record = ImprovementRecord(
            iteration=i,
            date_range=f"{since}~{until}",
            quality_score=score,
            completeness=completeness,
            chinese_correctness=chinese_correctness,
            layer_breakdown=layer_breakdown,
            issues=issues,
            prompt_adjustments=adjustments,
            report_sample=report_text[:500],
        )
        log_improvement(record)
        results.append(
            {
                "iteration": i,
                "score": score.overall,
                "completeness": completeness,
                "chinese_correctness": chinese_correctness,
                "issues": issues,
            }
        )

        if i % 10 == 0:
            logger.info("Completed %d/%d iterations", i, iterations)

    return {
        "iterations": iterations,
        "results": results,
        "avg_quality": sum(r["score"] for r in results) / len(results)
        if results
        else 0,
        "avg_completeness": sum(r.get("completeness", 0) for r in results)
        / len(results)
        if results
        else 0,
        "avg_chinese_correctness": sum(r.get("chinese_correctness", 0) for r in results)
        / len(results)
        if results
        else 0,
    }
