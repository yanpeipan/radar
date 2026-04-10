from src.llm.chains import get_entity_topic_chain, get_ner_chain, get_tldr_chain


def test_get_ner_chain_returns_runnable():
    chain = get_ner_chain()
    assert chain is not None
    assert hasattr(chain, "invoke")


def test_get_entity_topic_chain_returns_runnable():
    chain = get_entity_topic_chain()
    assert chain is not None
    assert hasattr(chain, "invoke")


def test_get_tldr_chain_returns_runnable():
    chain = get_tldr_chain()
    assert chain is not None
    assert hasattr(chain, "invoke")
