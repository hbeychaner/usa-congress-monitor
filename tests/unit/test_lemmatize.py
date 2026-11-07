import logging
import time
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
import spacy
from spacy.language import Language
from spacy.tokens import Doc

import cdm.utils.lemmatize as lemmatize_module
from cdm.config import LemmatizationConfig
from cdm.config.app_config import LemmaExcludedComponent
from cdm.utils.lemmatize import (
    SpacyLemmatizer,
    lemmatize_texts,
    try_lemmatize_query,
)


class PipeProbe:
    def __init__(self) -> None:
        self.language = MagicMock(spec=Language)
        self.language.max_length = 1_000_000
        self.language.memory_zone.side_effect = self.zone
        self.language.pipe.side_effect = self.pipe
        self.loader = MagicMock(return_value=self.language)
        self.vocab = spacy.blank("en").vocab
        self.inside = False
        self.zones = 0
        self.seen: list[str] = []
        self.batches: list[int] = []

    @contextmanager
    def zone(self) -> Iterator[None]:
        assert not self.inside
        self.inside = True
        self.zones += 1
        try:
            yield
        finally:
            self.inside = False

    def pipe(self, texts: Iterable[str], *, batch_size: int) -> Iterator[Doc]:
        assert self.inside
        self.batches.append(batch_size)
        for text in texts:
            assert self.inside
            self.seen.append(text)
            time.sleep(0.001)
            doc = Doc(self.vocab, words=[*text.split(), "."])
            for token in doc:
                token.lemma_ = token.text.upper()
            yield doc

    def service(self, settings: LemmatizationConfig | None = None) -> SpacyLemmatizer:
        return SpacyLemmatizer(
            settings or LemmatizationConfig(), self.loader,
            logging.getLogger(__name__),
        )


def test_lemmatizes_strings_inside_one_memory_zone_with_bounded_batches() -> None:
    probe = PipeProbe()
    service = probe.service()
    assert service.lemmatize(["Passed House", "", "the Border Acts"]) == [
        "passed house", "", "border acts",
    ]
    assert probe.zones == 1
    assert not probe.inside
    assert probe.batches == [1]
    probe.loader.assert_called_once_with(
        "en_core_web_md",
        exclude=(LemmaExcludedComponent.PARSER, LemmaExcludedComponent.NER),
    )


def test_no_input_does_not_load_model_or_create_zone() -> None:
    probe = PipeProbe()
    assert probe.service().lemmatize([]) == []
    probe.loader.assert_not_called()
    assert probe.zones == 0


def test_prefork_warmup_loads_only_the_shared_model_without_inference() -> None:
    probe = PipeProbe()
    service = probe.service()
    service.warm()
    service.warm()
    assert probe.loader.call_count == 1
    assert probe.zones == 0
    probe.language.pipe.assert_not_called()
    assert service.lemmatize(["House Acts"]) == ["house acts"]
    assert probe.loader.call_count == 1


def test_character_limit_preserves_the_existing_head_only_contract() -> None:
    probe = PipeProbe()
    probe.language.max_length = 5
    service = probe.service(LemmatizationConfig(lemma_max_chars=4))
    assert service.lemmatize(["Passed House"]) == ["pass"]
    assert probe.seen == ["Pass"]


def test_concurrent_calls_do_not_overlap_zones_and_load_model_only_once() -> None:
    probe = PipeProbe()
    service = probe.service()
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(service.lemmatize, [["House Acts"]] * 8))
    assert outputs == [["house acts"]] * 8
    assert probe.zones == 8
    assert not probe.inside
    assert probe.loader.call_count == 1


def test_model_failure_leaves_the_zone_closed_and_is_explicit() -> None:
    probe = PipeProbe()
    probe.loader.side_effect = OSError("model missing")
    with pytest.raises(RuntimeError, match="not installed"):
        probe.service().lemmatize(["Border"])
    assert probe.zones == 0


def test_query_failure_keeps_the_logged_best_effort_contract(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = PipeProbe()
    probe.loader.side_effect = OSError("model missing")
    with caplog.at_level(logging.WARNING):
        assert probe.service().try_query("Border") == ""
    assert "Query lemmatization unavailable" in caplog.text


def test_public_facades_and_blank_query_preserve_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = PipeProbe()
    service = probe.service()
    monkeypatch.setattr(lemmatize_module, "_default_lemmatizer", service)
    assert try_lemmatize_query("   ") == ""
    probe.loader.assert_not_called()
    assert lemmatize_texts(["Passed House"]) == ["passed house"]
    assert try_lemmatize_query("Border Acts") == "border acts"


def test_inference_failure_always_exits_its_memory_zone() -> None:
    probe = PipeProbe()
    probe.language.pipe.side_effect = ValueError("invalid input")
    with pytest.raises(ValueError, match="invalid input"):
        probe.service().lemmatize(["Border"])
    assert not probe.inside
    assert probe.zones == 1


def test_real_language_zone_releases_transient_lexemes_and_strings() -> None:
    language = spacy.blank("en")
    strings = len(language.vocab.strings)
    service = SpacyLemmatizer(
        LemmatizationConfig(), MagicMock(return_value=language),
        logging.getLogger(__name__),
    )
    for text in ("zztransientlexemealpha", "zztransientlexemebeta"):
        assert text not in language.vocab
        assert service.lemmatize([text]) == [""]
        assert text not in language.vocab
        assert len(language.vocab.strings) == strings
