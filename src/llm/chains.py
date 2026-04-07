"""LangChain LCEL chains for report generation."""

from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.llm.core import LLMConfig


# Lazy-loaded model - avoid importing litellm at module level
def _get_model():
    from litellm import ainvoke

    config = LLMConfig.from_settings()
    model_name = f"{config.provider}/{config.model}"
    return lambda prompt, **kwargs: ainvoke(model_name, prompt, **kwargs)


# Article classification chain using LCEL
CLASSIFY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Classify this article into ONE of the following categories:
- AI应用 (Application): AI products, tools, and services used by end users
- AI模型 (Model): AI model releases, benchmarks, research papers, training methods
- AI基础设施 (Infrastructure): Cloud platforms, MLOps tools, deployment, APIs
- 芯片 (Chip): AI hardware, GPUs, custom silicon, semiconductor news
- 能源 (Energy): AI energy consumption, data center power, carbon, renewable energy""",
        ),
        (
            "human",
            "Article Title: {title}\nArticle Content: {content}\n\nReturn ONLY the category name.",
        ),
    ]
)


def get_classify_chain():
    """Returns LCEL chain for article classification."""
    model = _get_model()
    return CLASSIFY_PROMPT | model | StrOutputParser()


# Layer summary generation chain
LAYER_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", "You are writing a concise summary for a news report section."),
        (
            "human",
            """The following articles are about: {layer}

Articles:
{article_list}

Write 2-3 paragraphs summarizing the key trends and insights from these articles.
Focus on the most important developments. Use professional Chinese.

Summary:""",
        ),
    ]
)


def get_layer_summary_chain():
    """Returns LCEL chain for layer summary generation."""
    model = _get_model()
    return LAYER_SUMMARY_PROMPT | model | StrOutputParser()


# Report quality evaluation chain
EVALUATE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a professional news report editor. Evaluate report quality objectively.",
        ),
        (
            "human",
            """Evaluate this daily report and score it 0-1 on overall quality.

Report:
{report}

Score only the number 0.0-1.0, nothing else. Consider: coherence, relevance, depth, structure.""",
        ),
    ]
)


def get_evaluate_chain():
    """Returns LCEL chain for report quality evaluation."""
    model = _get_model()
    return EVALUATE_PROMPT | model | StrOutputParser()
