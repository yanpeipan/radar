"""LLM module — core client and quality evaluation."""

from src.llm.core import (
    DailyCapExceeded,
    LLMClient,
    LLMConfig,
    LLMError,
    ProviderUnavailable,
    batch_summarize_articles,
    get_llm_client,
    llm_complete,
    reset_llm_client,
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
    "ProviderUnavailable",
    "get_llm_client",
    "reset_llm_client",
    "llm_complete",
    "batch_summarize_articles",
    # evaluator
    "QualityScore",
    "ImprovementRecord",
    "evaluate_report",
    "suggest_improvements",
    "log_improvement",
]
