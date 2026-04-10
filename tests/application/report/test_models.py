import pytest

from src.application.report.models import (
    ArticleEnriched,
    EntityTag,
    EntityTopic,
    ReportData,
)


def test_entity_tag_fields():
    tag = EntityTag(name="Google Gemma 4", type="PRODUCT", normalized="google_gemma_4")
    assert tag.name == "Google Gemma 4"
    assert tag.type == "PRODUCT"
    assert tag.normalized == "google_gemma_4"


def test_article_enriched_default_fields():
    article = ArticleEnriched(
        id="a1",
        title="Test",
        link="http://x.com",
        summary="",
        quality_score=0.8,
        feed_weight=0.7,
        published_at="2026-04-09",
        feed_id="f1",
    )
    assert article.entities == []
    assert article.dimensions == []


def test_entity_topic_fields():
    topic = EntityTopic(
        entity_id="google_gemma_4",
        entity_name="Google Gemma 4",
        layer="AI模型",
        headline="Gemma 4发布",
        dimensions={"release": []},
        articles_count=10,
        signals=["open source"],
        tldr="",
        quality_weight=8.0,
    )
    assert topic.entity_id == "google_gemma_4"
    assert topic.articles_count == 10
    assert topic.quality_weight == 8.0


def test_report_data_fields():
    data = ReportData(
        tldr_top10=[],
        by_layer={},
        by_dimension={},
        deep_dive=[],
        date_range={"since": "2026-04-07", "until": "2026-04-10"},
        target_lang="zh",
    )
    assert data.target_lang == "zh"
    assert data.date_range["since"] == "2026-04-07"
