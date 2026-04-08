"""LLM module — core client, chains, and quality evaluation.

Public API:
    from src.llm import LLMConfig, LLMClient, get_llm_client, llm_complete
    from src.llm import summarize_text, score_quality, extract_keywords
    from src.llm import evaluate_report
"""

from src.llm.core import (
    ContentTruncated,
    DailyCapExceeded,
    FeedWeightGated,
    LLMClient,
    LLMConfig,
    LLMError,
    ProviderUnavailable,
    compute_content_hash,
    extract_keywords,
    get_encoding_for_model,
    get_llm_client,
    llm_complete,
    reset_llm_client,
    score_quality,
    summarize_text,
    truncate_content,
)
from src.llm.evaluator import (
    ImprovementRecord,
    QualityScore,
    evaluate_report,
    log_improvement,
    suggest_improvements,
)

__all__ = [
    # core
    "LLMConfig",
    "LLMClient",
    "LLMError",
    "DailyCapExceeded",
    "ContentTruncated",
    "ProviderUnavailable",
    "FeedWeightGated",
    "get_llm_client",
    "reset_llm_client",
    "llm_complete",
    "summarize_text",
    "score_quality",
    "extract_keywords",
    "truncate_content",
    "get_encoding_for_model",
    "compute_content_hash",
    # evaluator
    "QualityScore",
    "ImprovementRecord",
    "evaluate_report",
    "suggest_improvements",
    "log_improvement",
]
