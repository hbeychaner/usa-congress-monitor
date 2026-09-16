import pytest

import cdm.utils.lemmatize as lemmatize_module
from cdm.utils.lemmatize import lemmatize_texts, try_lemmatize_query


class _FakeToken:
    def __init__(self, lemma, is_punct=False, is_space=False, is_stop=False):
        self.lemma_ = lemma
        self.is_punct = is_punct
        self.is_space = is_space
        self.is_stop = is_stop


class _FakeNlp:
    max_length = 1_000_000

    def pipe(self, texts):
        for text in texts:
            tokens = [_FakeToken(word.upper()) for word in text.split()]
            tokens.append(_FakeToken(".", is_punct=True))
            yield tokens


@pytest.fixture
def fake_nlp(monkeypatch):
    monkeypatch.setattr(lemmatize_module, "_get_nlp", lambda: _FakeNlp())


def test_lemmatize_texts_lowercases_and_drops_punctuation(fake_nlp):
    assert lemmatize_texts(["Passed House", ""]) == ["passed house", ""]


def test_lemmatize_texts_returns_empty_for_no_input():
    assert lemmatize_texts([]) == []


def test_try_lemmatize_query_returns_empty_when_model_unavailable(monkeypatch):
    def boom():
        raise RuntimeError("model missing")

    monkeypatch.setattr(lemmatize_module, "_get_nlp", boom)

    assert try_lemmatize_query("border security") == ""


def test_try_lemmatize_query_skips_blank_queries(fake_nlp):
    assert try_lemmatize_query("   ") == ""
    assert try_lemmatize_query("Border Acts") == "border acts"
