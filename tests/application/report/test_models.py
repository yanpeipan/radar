import pytest

from src.application.report.models import (
    ReportArticle,
    ReportCluster,
    ReportData,
)


def test_article_enriched_default_fields():
    article = ReportArticle(
        id="a1",
        feed_id="f1",
        feed_name="Test Feed",
        title="Test",
        link="http://x.com",
        guid="a1",
        published_at="2026-04-09",
        description="",
    )
    assert article.tags == []


def test_entity_topic_fields():
    topic = ReportCluster(
        title="Google Gemma 4",
        summary="Gemma 4发布",
        tags=[],
        children=[],
        articles=[],
    )
    assert topic.title == "Google Gemma 4"


def test_report_data_fields():
    data = ReportData(
        clusters={},
        date_range={"since": "2026-04-07", "until": "2026-04-10"},
        target_lang="zh",
    )
    assert data.target_lang == "zh"
    assert data.date_range["since"] == "2026-04-07"
