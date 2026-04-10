import pytest

from src.application.report.ner import NERExtractor, normalize_entity


def test_normalize_entity():
    assert normalize_entity("Google Gemma 4", "PRODUCT") == "google_gemma_4"
    assert normalize_entity("gemma-4", "PRODUCT") == "gemma_4"
    assert normalize_entity("OpenAI", "ORG") == "openai"
    assert normalize_entity("Sam Altman", "PERSON") == "sam_altman"


def test_ner_extractor_batch_size():
    ner = NERExtractor(batch_size=10)
    assert ner.batch_size == 10


def test_ner_extractor_default_batch_size():
    ner = NERExtractor()
    assert ner.batch_size == 10


def test_normalize_entity_weird_chars():
    assert normalize_entity("OpenAI's Model", "PRODUCT") == "openais_model"
    assert normalize_entity("  Google  ", "ORG") == "google"
