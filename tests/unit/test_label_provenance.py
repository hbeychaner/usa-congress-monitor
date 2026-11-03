from unittest.mock import Mock

import numpy as np
import pytest
import requests
from elasticsearch import Elasticsearch

from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.config import OllamaConfig, PerspectiveConfig
from cdm.contracts.labels import (
    LabelFallbackReason,
    LabelProvenance,
    LabelResult,
    LabelSource,
)
from cdm.perspectives.builder import PerspectiveBuilder
from cdm.perspectives.clustering import ClusterResult, PerspectiveClusterer
from cdm.perspectives.evidence import SubjectContrast, TermEvidence
from cdm.perspectives.labeler import PerspectiveLabeler
from cdm.perspectives.models import PerspectiveBill
from cdm.perspectives.summarizer import ApproachSummarizer
from cdm.perspectives.terms import DistinctiveTerms
from cdm.store.topic_publication import TopicPublicationStore
from cdm.utils.json_types import JsonObject
from cdm.utils.metasubject_namer import OllamaMetasubjectNamer
from cdm.utils.metasubjects import (
    LargestTopicNamer,
    Metasubject,
    MetasubjectBuilder,
    MetasubjectOverrides,
    StableIdMatcher,
    TopicVector,
)
from cdm.utils.ollama_client import OllamaClient
from cdm.utils.topic_labeler import TopicLabeler
from cdm.utils.topic_records import TopicSummaryRow


def test_unavailable_topic_labels_retain_a_recorded_fallback() -> None:
    ollama = Mock(spec=OllamaClient)
    ollama.is_available.return_value = False
    topic = TopicSummaryRow(
        topic_id=0, name="0_health_care", size=20, top_words=["health", "care"]
    )

    labels = TopicLabeler(ollama).label_topics([topic], {})

    assert 0 in labels
    assert labels[0].model_dump(mode="json") == {
        "label": "health care",
        "label_source": "keywords",
        "fallback_reason": "unavailable",
    }
    ollama.chat.assert_not_called()


class OllamaHarness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.response = Mock(spec=requests.Response)
        self.response.json.return_value = {"message": {"content": "Hospital Funding"}}
        self.post = Mock(return_value=self.response)
        self.probe = Mock(return_value=self.response)
        monkeypatch.setattr("cdm.utils.ollama_client.requests.post", self.post)
        monkeypatch.setattr("cdm.utils.ollama_client.requests.get", self.probe)
        self.client = OllamaClient(OllamaConfig())


@pytest.fixture
def ollama(monkeypatch: pytest.MonkeyPatch) -> OllamaHarness:
    return OllamaHarness(monkeypatch)


def test_accepted_topic_label_is_llm_generated(ollama: OllamaHarness) -> None:
    ollama.response.json.return_value = {
        "message": {"content": '"Topic title: Hospital Funding."'}
    }

    label = TopicLabeler(ollama.client).generate(["health"], ["A hospital bill"])

    assert label == LabelResult(label="Hospital Funding", label_source=LabelSource.LLM)


@pytest.mark.parametrize("available", [True, False])
def test_missing_keywords_preserve_the_existing_human_readable_topic_name(
    ollama: OllamaHarness, available: bool
) -> None:
    if not available:
        ollama.probe.side_effect = requests.ConnectionError()
    ollama.response.json.return_value = {"message": {"content": ""}}
    topic = TopicSummaryRow(topic_id=1, name="1_health_care", size=20)

    label = TopicLabeler(ollama.client).label_topics([topic], {})[1]

    assert label.label == "health care"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"content": "Wrong envelope"},
        {"message": None},
        {"message": {"content": ["not", "text"]}},
        {"message": {"content": ""}},
        {"message": {"content": " ".join(["word"] * 9)}},
    ],
)
def test_invalid_replies_record_safe_keyword_fallbacks(
    ollama: OllamaHarness, body: JsonObject
) -> None:
    ollama.response.json.return_value = body

    label = TopicLabeler(ollama.client).generate(["health", "care"], [])

    assert label == LabelResult(
        label="health care",
        label_source=LabelSource.KEYWORDS,
        fallback_reason=LabelFallbackReason.INVALID_RESPONSE,
    )


def test_invalid_json_does_not_leak_server_text(
    ollama: OllamaHarness, caplog: pytest.LogCaptureFixture
) -> None:
    ollama.response.json.side_effect = ValueError("private server body")

    label = TopicLabeler(ollama.client).generate(["health"], [])

    assert label.fallback_reason == LabelFallbackReason.INVALID_RESPONSE
    assert "private server body" not in label.model_dump_json()
    assert "private server body" not in caplog.text


@pytest.mark.parametrize(
    "error", [requests.ConnectionError, requests.Timeout, requests.HTTPError]
)
def test_request_failures_are_safe_and_preserve_usable_labels(
    ollama: OllamaHarness,
    caplog: pytest.LogCaptureFixture,
    error: type[requests.RequestException],
) -> None:
    ollama.post.side_effect = error("private dependency diagnostic")

    label = TopicLabeler(ollama.client).generate(["health"], [])

    assert label.label == "health"
    assert label.label_source == LabelSource.KEYWORDS
    assert label.fallback_reason == LabelFallbackReason.REQUEST_FAILED
    assert "private dependency diagnostic" not in caplog.text
    assert "private dependency diagnostic" not in label.model_dump_json()


def test_unexpected_programming_errors_are_not_successful_fallbacks(
    ollama: OllamaHarness,
) -> None:
    ollama.post.side_effect = RuntimeError("implementation error")

    with pytest.raises(RuntimeError, match="implementation error"):
        TopicLabeler(ollama.client).generate(["health"], [])


@pytest.mark.parametrize("enabled", [True, False])
def test_perspective_probe_failure_is_distinct_from_disabled_labels(
    ollama: OllamaHarness, enabled: bool
) -> None:
    ollama.probe.side_effect = requests.ConnectionError()
    labeler = PerspectiveLabeler(ollama.client, enabled=enabled)

    label = labeler.label("Health", ["hospital", "funding"], ["A bill"])

    assert label.label == "hospital funding"
    assert label.label_source == LabelSource.KEYWORDS
    assert label.fallback_reason == (
        LabelFallbackReason.UNAVAILABLE if enabled else LabelFallbackReason.DISABLED
    )
    ollama.post.assert_not_called()
    assert ollama.probe.call_count == int(enabled)


def test_perspective_builder_keeps_generated_label_provenance(
    ollama: OllamaHarness,
) -> None:
    ollama.post.side_effect = requests.Timeout()
    builder = PerspectiveBuilder(
        PerspectiveConfig(),
        Mock(spec=PerspectiveClusterer),
        Mock(spec=DistinctiveTerms),
        Mock(spec=TermEvidence),
        Mock(spec=SubjectContrast),
        PerspectiveLabeler(ollama.client),
        Mock(spec=ApproachSummarizer),
    )
    bills = [PerspectiveBill(doc_id="bill", title="A bill", text="Hospital funding")]
    clusters = ClusterResult(
        labels=np.array([0], dtype=np.intp),
        silhouette=0.8,
        stability=0.9,
        features=np.array([[1.0, 0.0]], dtype=np.float32),
    )

    perspective = builder._perspective(
        119, 1, "Health", 0, clusters, bills, ["hospital", "funding"]
    )

    assert perspective.label == "hospital funding"
    assert perspective.label_source == LabelSource.KEYWORDS
    assert perspective.fallback_reason == LabelFallbackReason.REQUEST_FAILED


def test_summary_consumer_uses_typed_reply_without_changing_optional_behavior(
    ollama: OllamaHarness,
) -> None:
    summarizer = ApproachSummarizer(ollama.client)
    assert (
        summarizer.summarize("Health", "group", ["hospital"], [], [])
        == "Hospital Funding"
    )
    ollama.post.side_effect = requests.Timeout()
    assert summarizer.summarize("Health", "group", ["hospital"], [], []) == ""


def topic_vector() -> TopicVector:
    return TopicVector(topic_id=0, size=20, label="Health", vector=np.array([1.0, 0.0]))


@pytest.mark.parametrize("valid", [True, False])
def test_metasubject_namer_records_llm_or_largest_topic(
    ollama: OllamaHarness, valid: bool
) -> None:
    ollama.response.json.return_value = {
        "message": {"content": "Hospital Funding" if valid else ""}
    }

    label = OllamaMetasubjectNamer(ollama.client).name([topic_vector()])

    assert label.label == ("Hospital Funding" if valid else "Health")
    assert label.label_source == (
        LabelSource.LLM if valid else LabelSource.LARGEST_TOPIC
    )
    assert label.fallback_reason == (
        None if valid else LabelFallbackReason.INVALID_RESPONSE
    )


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (LabelSource.LLM, None),
        (LabelSource.LARGEST_TOPIC, LabelFallbackReason.REQUEST_FAILED),
        (LabelSource.UNKNOWN, None),
    ],
)
def test_carried_metasubject_names_keep_their_actual_origin(
    source: LabelSource, reason: LabelFallbackReason | None
) -> None:
    previous = Metasubject(
        metasubject_id=7,
        name="Previous name",
        topic_ids=[5],
        size=20,
        top_words=[],
        centroid=[1.0, 0.0],
        label_source=source,
        fallback_reason=reason,
    )
    namer = Mock(spec=LargestTopicNamer)
    group = MetasubjectBuilder(namer, StableIdMatcher(0.85), 1).build(
        [topic_vector()], [previous]
    )[0]

    assert group.name == previous.name
    assert group.label_source == source
    assert group.fallback_reason == reason
    namer.name.assert_not_called()


def test_override_replaces_old_fallback_metadata() -> None:
    namer = Mock(spec=LargestTopicNamer)
    builder = MetasubjectBuilder(
        namer,
        StableIdMatcher(0.85),
        1,
        MetasubjectOverrides(names={1: "Operator choice"}),
    )

    group = builder.build([topic_vector()])[0]

    assert group.name == "Operator choice"
    assert group.label_source == LabelSource.OVERRIDE
    assert group.fallback_reason is None
    namer.name.assert_not_called()


@pytest.mark.parametrize("kind", ["topic", "metasubject"])
@pytest.mark.parametrize("legacy", [True, False])
def test_primary_read_models_preserve_origin_and_do_not_invent_legacy_lineage(
    kind: str, legacy: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    source: JsonObject = {
        "topic_id": 0,
        "metasubject_id": 1,
        "name": "Health",
        "label": "Health",
        "size": 20,
    }
    if not legacy:
        source.update(
            label_source=LabelSource.KEYWORDS,
            fallback_reason=LabelFallbackReason.UNAVAILABLE,
        )
    service = TopicService(
        Mock(spec=Elasticsearch),
        "analysis",
        Mock(spec=SubjectService),
        Mock(spec=TopicPublicationStore),
    )
    monkeypatch.setattr(
        service, "_search", Mock(return_value={"hits": {"hits": [{"_source": source}]}})
    )

    summary = (
        service.topic_summaries("v1")[0]
        if kind == "topic"
        else service.metasubject_summaries("v1")[1]
    )

    assert summary.label_source == (
        LabelSource.UNKNOWN if legacy else LabelSource.KEYWORDS
    )
    assert summary.fallback_reason == (
        None if legacy else LabelFallbackReason.UNAVAILABLE
    )
    wire = summary.model_dump(mode="json")
    assert wire["label_source"] == summary.label_source
    assert wire["fallback_reason"] == summary.fallback_reason


def test_legacy_provenance_is_explicit_in_serialization() -> None:
    assert LabelProvenance().model_dump(mode="json") == {
        "label_source": "unknown",
        "fallback_reason": None,
    }
