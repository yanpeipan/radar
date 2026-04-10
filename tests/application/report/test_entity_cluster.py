import pytest

from src.application.report.entity_cluster import EntityClusterer, classify_dimensions
from src.application.report.models import ArticleEnriched, EntityTag


def test_classify_dimensions_release():
    article = ArticleEnriched(
        id="1",
        title="Google Gemma 4 Released",
        link="",
        summary="",
        quality_score=0.8,
        feed_weight=0.7,
        published_at="",
        feed_id="f1",
        entities=[],
        dimensions=[],
    )
    dims = classify_dimensions(article)
    assert "release" in dims


def test_classify_dimensions_funding():
    article = ArticleEnriched(
        id="1",
        title="OpenAI Raises $10B",
        link="",
        summary="",
        quality_score=0.8,
        feed_weight=0.7,
        published_at="",
        feed_id="f1",
        entities=[],
        dimensions=[],
    )
    dims = classify_dimensions(article)
    assert "funding" in dims


def test_classify_dimensions_research():
    article = ArticleEnriched(
        id="1",
        title="New Research Paper on LLM",
        link="",
        summary="",
        quality_score=0.8,
        feed_weight=0.7,
        published_at="",
        feed_id="f1",
        entities=[],
        dimensions=[],
    )
    dims = classify_dimensions(article)
    assert "research" in dims


def test_classify_dimensions_ecosystem_default():
    article = ArticleEnriched(
        id="1",
        title="Random Article",
        link="",
        summary="",
        quality_score=0.8,
        feed_weight=0.7,
        published_at="",
        feed_id="f1",
        entities=[],
        dimensions=[],
    )
    dims = classify_dimensions(article)
    assert dims == ["ecosystem"]


def test_entity_clusterer_initialized():
    ec = EntityClusterer(large_event_threshold=50, max_entities=50)
    assert ec.large_event_threshold == 50
    assert ec.max_entities == 50


def test_entity_clusterer_default():
    ec = EntityClusterer()
    assert ec.max_entities == 50
    assert ec.large_event_threshold == 50
