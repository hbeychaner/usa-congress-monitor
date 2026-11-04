from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
from elasticsearch import Elasticsearch

from cdm.config.topic_analysis import TopicKind, TopicTrainingOptions
from cdm.contracts.labels import LabelFallbackReason, LabelResult, LabelSource
from cdm.store.embedding_store import EmbeddingStore
from cdm.store.metasubject_repository import MetasubjectRepository
from cdm.store.topic_publication import (
    CompletedTopicRun,
    TopicPublicationSnapshot,
    TopicPublicationStore,
    TopicRunSpecification,
)
from cdm.topics.training import TopicTrainingJob, TrainingProgress
from cdm.utils.json_types import JsonObject
from cdm.utils.metasubjects import (
    AssignedBy,
    LargestTopicNamer,
    Metasubject,
    MetasubjectAssigner,
    MetasubjectAssignment,
    MetasubjectBuilder,
    MetasubjectOverTimeRow,
    QuarterlyTrendBuilder,
    TopicVector,
)
from cdm.utils.topic_labeler import TopicLabeler
from cdm.utils.topic_modeler import TopicAssignment, TopicModeler
from cdm.utils.topic_records import TopicSummaryRow, TopicTimeBin
from cdm.workers.runtime import WorkerContainer
from scripts import train_topic_model


class TrainingHarness:
    def __init__(self, options: TopicTrainingOptions) -> None:
        self.client = Mock(spec=Elasticsearch)
        self.publications = Mock(spec=TopicPublicationStore, index="analysis")
        self.publications.snapshot.return_value = None
        self.repository = Mock(spec=MetasubjectRepository)
        self.repository.latest.return_value = []
        self.modeler = Mock(
            spec=TopicModeler,
            embedding_store=None
            if options.preview or options.publish_version
            else Mock(
                spec=EmbeddingStore,
                model="configured-model",
                index="isolated-cache",
            ),
            embedding_model_name="configured-model",
        )
        self.modeler.document_embeddings.return_value = np.array([[1.0, 0.0]])
        self.modeler.fit.return_value = [
            TopicAssignment(doc_id="bill:118:hr:1", topic_id=0, probability=0.9)
        ]
        self.modeler.topic_summaries.return_value = [
            TopicSummaryRow(topic_id=0, name="health", size=1)
        ]
        self.modeler.topic_vectors.return_value = [
            TopicVector(
                topic_id=0,
                size=1,
                label="health",
                top_words=[],
                vector=np.array([1.0, 0.0]),
            )
        ]
        self.modeler.topics_over_time.return_value = [
            TopicTimeBin(
                topic_id=0, words="health", frequency=1, timestamp="2025-01-01"
            )
        ]
        self.groups = [
            Metasubject(
                metasubject_id=7,
                name="Health",
                topic_ids=[0],
                size=1,
                top_words=[],
                centroid=[1.0, 0.0],
            )
        ]
        self.builder = Mock(spec=MetasubjectBuilder)
        self.builder.build.return_value = self.groups
        self.assigner = Mock(spec=MetasubjectAssigner)
        self.assigner.assign.return_value = [
            MetasubjectAssignment(
                doc_id="bill:118:hr:1",
                metasubject_id=7,
                confidence=1.0,
                assigned_by=AssignedBy.CLUSTER,
                low_confidence=False,
            )
        ]
        self.assigner.with_sizes.return_value = self.groups
        self.labeler = Mock(spec=TopicLabeler)
        self.labeler.label_topics.return_value = {
            0: LabelResult(
                label="health",
                label_source=LabelSource.KEYWORDS,
                fallback_reason=LabelFallbackReason.UNAVAILABLE,
            )
        }
        self.progress: list[TrainingProgress] = []
        self.actions: list[JsonObject] = []
        self.specification: TopicRunSpecification | None = None
        self.publications.write.side_effect = self._write
        self.publications.publish.side_effect = self._publish
        self.job = TopicTrainingJob(
            self.client,
            self.publications,
            self.repository,
            self.modeler,
            self.builder,
            lambda groups: self.assigner,
            options,
            self.progress.append,
            self.labeler,
        )

    def _write(
        self, specification: TopicRunSpecification, actions: Iterable[JsonObject]
    ) -> CompletedTopicRun:
        self.specification = specification
        self.actions = list(actions)
        return CompletedTopicRun.model_validate(
            {
                **specification.model_dump(),
                "completed_at": datetime.now(UTC),
            }
        )

    def _publish(
        self, version: str, expected: TopicPublicationSnapshot | None
    ) -> CompletedTopicRun:
        assert self.specification is not None
        assert self.specification.model_version == version
        assert expected is None
        return CompletedTopicRun.model_validate(
            {
                **self.specification.model_dump(),
                "completed_at": datetime.now(UTC),
            }
        )


@pytest.fixture
def corpus(monkeypatch: pytest.MonkeyPatch) -> Mock:
    scan = Mock(
        return_value=[
            {
                "_id": "bill:118:hr:1",
                "_source": {"title": "Health", "introduced_date": "2025-01-01"},
            }
        ]
    )
    monkeypatch.setattr("cdm.topics.training.scan", scan)
    return scan


def test_incompatible_publication_mapping_fails_before_fetch_or_fit(
    corpus: Mock,
) -> None:
    harness = TrainingHarness(TopicTrainingOptions())
    harness.publications.ensure_index.side_effect = ValueError("Incompatible mapping")
    with pytest.raises(ValueError, match="Incompatible mapping"):
        harness.job.execute()
    corpus.assert_not_called()
    harness.modeler.fit.assert_not_called()


def test_preview_never_initializes_the_publication_mapping(corpus: Mock) -> None:
    harness = TrainingHarness(TopicTrainingOptions(dry_run=True))
    harness.job.execute()
    harness.publications.ensure_index.assert_not_called()


@pytest.mark.parametrize(
    "label",
    [
        None,
        LabelResult(label="Hospital Funding", label_source=LabelSource.LLM),
        LabelResult(
            label="health",
            label_source=LabelSource.KEYWORDS,
            fallback_reason=LabelFallbackReason.REQUEST_FAILED,
        ),
    ],
)
def test_training_indexes_label_provenance_without_changing_publication(
    tmp_path: Path, corpus: Mock, label: LabelResult | None
) -> None:
    harness = TrainingHarness(TopicTrainingOptions(model_dir=tmp_path))
    if label is None:
        harness.job._labeler = None
    else:
        harness.labeler.label_topics.return_value = {0: label}

    completed = harness.job.execute()

    assert completed is not None
    topic = next(
        action for action in harness.actions if action["kind"] == TopicKind.TOPIC
    )
    assert topic["label_source"] == (
        label.label_source if label else LabelSource.KEYWORDS
    )
    assert topic.get("fallback_reason") == (
        label.fallback_reason if label else LabelFallbackReason.DISABLED
    )
    if label is not None:
        assert topic["label"] == label.label
    harness.publications.publish.assert_called_once()


def test_missing_label_results_fail_before_any_persistent_output(corpus: Mock) -> None:
    harness = TrainingHarness(TopicTrainingOptions())
    harness.labeler.label_topics.return_value = {}

    with pytest.raises(ValueError, match="label results do not cover"):
        harness.job.execute()

    harness.modeler.save.assert_not_called()
    harness.publications.write.assert_not_called()
    harness.publications.publish.assert_not_called()


class TestReadOnlyPreviews:
    @pytest.mark.parametrize(
        "options",
        [TopicTrainingOptions(dry_run=True), TopicTrainingOptions(max_docs=1)],
    )
    def test_preview_has_no_persistent_output_or_llm_calls(
        self, tmp_path: Path, corpus: Mock, options: TopicTrainingOptions
    ) -> None:
        harness = TrainingHarness(
            options.model_copy(update={"model_dir": tmp_path / "models"})
        )

        assert harness.job.execute() is None

        harness.modeler.save.assert_not_called()
        harness.publications.write.assert_not_called()
        harness.publications.publish.assert_not_called()
        harness.labeler.label_topics.assert_not_called()
        assert not (tmp_path / "models").exists()
        assert harness.progress[-1].progress == 1.0
        assert harness.progress[-1].model_version is None
        assert corpus.call_args.kwargs["allow_partial_search_results"] is False

    def test_preview_rejects_an_accidentally_injected_writable_cache(self) -> None:
        harness = TrainingHarness(TopicTrainingOptions(max_docs=1))
        harness.modeler.embedding_store = Mock()

        with pytest.raises(ValueError, match="writable embedding cache"):
            harness.job.execute()

        harness.modeler.fit.assert_not_called()

    @pytest.mark.parametrize("arguments", [["--max-docs", "1"], ["--dry-run"]])
    def test_cli_disables_cache_and_llm_collaborators(
        self, arguments: list[str]
    ) -> None:
        container = WorkerContainer(train_topic_model.get_config())
        container.embedding_store = Mock()
        container.__dict__.update(
            elastic_client=Mock(),
            metasubject_repository=Mock(),
            topic_publications=Mock(),
            metasubject_override_store=Mock(),
        )
        with patch("cdm.workers.runtime.TopicModeler") as modeler:
            job = container.topic_training_job(
                train_topic_model.parse_args(arguments), Mock()
            )

        container.embedding_store.assert_not_called()
        assert "ollama_client" not in container.__dict__
        assert isinstance(job._builder.namer, LargestTopicNamer)
        assert job._builder.disambiguator is None
        assert modeler.call_args.kwargs["embedding_store"] is None
        assert job._labeler is None

    @pytest.mark.parametrize("limit", ["0", "-1"])
    def test_invalid_caps_are_not_mistaken_for_full_runs(self, limit: str) -> None:
        with pytest.raises(SystemExit) as error:
            train_topic_model.parse_args(["--max-docs", limit])
        assert error.value.code == 2

    @pytest.mark.parametrize("flag", ["--embedding-model", "--publish-version"])
    def test_explicit_blank_models_do_not_fall_back_to_default_training(
        self, flag: str
    ) -> None:
        with pytest.raises(SystemExit) as error:
            train_topic_model.parse_args([flag, ""])
        assert error.value.code == 2

    def test_preview_cannot_publish_an_existing_version(self) -> None:
        with pytest.raises(SystemExit):
            train_topic_model.parse_args(
                ["--max-docs", "1", "--publish-version", "old"]
            )


class TestFullTraining:
    @pytest.mark.parametrize("model", [None, "another-model"])
    def test_full_training_rejects_missing_or_incompatible_cache(
        self, model: str | None
    ) -> None:
        harness = TrainingHarness(TopicTrainingOptions())
        harness.modeler.embedding_store = (
            Mock(spec=EmbeddingStore, model=model) if model else None
        )
        with pytest.raises(ValueError, match="requires a cache"):
            harness.job.execute()
        harness.modeler.fit.assert_not_called()
        harness.modeler.save.assert_not_called()
        harness.publications.write.assert_not_called()

    def test_explicit_rollback_does_not_fit_or_save_a_model(self) -> None:
        harness = TrainingHarness(TopicTrainingOptions(publish_version="retained"))
        harness.publications.publish.side_effect = None
        harness.publications.publish.return_value = Mock(
            spec=CompletedTopicRun, model_version="retained"
        )

        assert harness.job.execute() is harness.publications.publish.return_value

        harness.publications.publish.assert_called_once_with("retained", None)
        harness.modeler.fit.assert_not_called()
        harness.modeler.save.assert_not_called()
        harness.repository.latest.assert_not_called()

    def test_validated_outputs_are_written_before_pointer_switch(
        self, tmp_path: Path, corpus: Mock
    ) -> None:
        harness = TrainingHarness(TopicTrainingOptions(model_dir=tmp_path))

        run = harness.job.execute()

        assert run is not None
        assert len(harness.actions) == run.counts.total == 5
        assert run.corpus_size == run.dated_documents == 1
        assert run.min_congress == 113
        assert run.embedding_model == harness.modeler.embedding_model_name
        assert run.embedding_cache is not None
        assert run.embedding_cache.index == "isolated-cache"
        assert run.embedding_cache.dimensions == 2
        by_kind: dict[TopicKind, JsonObject] = {}
        identifiers: set[str] = set()
        for action in harness.actions:
            kind, identifier = action["kind"], action["_id"]
            assert isinstance(kind, str)
            assert isinstance(identifier, str)
            by_kind[TopicKind(kind)] = action
            identifiers.add(identifier)
        assert set(by_kind) == set(run.counts.by_kind())
        assert len(identifiers) == run.counts.total
        for action in harness.actions:
            assert action["_index"] == "analysis"
            assert action["model_version"] == run.model_version
            assert action["trained_at"] == run.trained_at.isoformat()
        assert by_kind[TopicKind.TOPIC]["_id"] == f"topic:{run.model_version}:0"
        assert by_kind[TopicKind.OVER_TIME]["_id"] == f"over_time:{run.model_version}:0"
        assert (
            by_kind[TopicKind.METASUBJECT]["_id"]
            == f"metasubject:{run.model_version}:7"
        )
        assert by_kind[TopicKind.METASUBJECT_OVER_TIME]["_id"] == (
            f"metasubject_over_time:{run.model_version}:0"
        )
        assignment = by_kind[TopicKind.ASSIGNMENT]
        assert assignment["_id"] == f"assignment:{run.model_version}:bill:118:hr:1"
        assert assignment["metasubject_id"] == 7
        assert assignment["metasubject_confidence"] == 1.0
        assert assignment["assigned_by"] == AssignedBy.CLUSTER
        assert assignment["low_confidence"] is False
        harness.modeler.save.assert_called_once()
        harness.publications.publish.assert_called_once_with(run.model_version, None)
        assert harness.progress[-1].progress == 1.0

    def test_incomplete_assignments_are_rejected_before_save_or_write(
        self, tmp_path: Path, corpus: Mock
    ) -> None:
        harness = TrainingHarness(TopicTrainingOptions(model_dir=tmp_path))
        harness.modeler.fit.return_value = []

        with pytest.raises(ValueError, match="exactly one assignment"):
            harness.job.execute()

        harness.modeler.save.assert_not_called()
        harness.publications.write.assert_not_called()
        harness.publications.publish.assert_not_called()

    def test_incomplete_trends_are_rejected(self, corpus: Mock) -> None:
        harness = TrainingHarness(TopicTrainingOptions())
        harness.modeler.topics_over_time.return_value = []

        with pytest.raises(ValueError, match="dated corpus"):
            harness.job.execute()

        harness.publications.publish.assert_not_called()

    @pytest.mark.parametrize(
        "kind", [TopicKind.OVER_TIME, TopicKind.METASUBJECT_OVER_TIME]
    )
    def test_unknown_trend_references_are_rejected_even_with_zero_frequency(
        self, corpus: Mock, monkeypatch: pytest.MonkeyPatch, kind: TopicKind
    ) -> None:
        harness = TrainingHarness(TopicTrainingOptions())
        if kind == TopicKind.OVER_TIME:
            harness.modeler.topics_over_time.return_value.append(
                TopicTimeBin(
                    topic_id=99, words="unknown", frequency=0, timestamp="2025-01-01"
                )
            )
        else:
            monkeypatch.setattr(
                QuarterlyTrendBuilder,
                "build",
                Mock(
                    return_value=[
                        MetasubjectOverTimeRow(
                            metasubject_id=7, frequency=1, timestamp="2025-01-01"
                        ),
                        MetasubjectOverTimeRow(
                            metasubject_id=99, frequency=0, timestamp="2025-01-01"
                        ),
                    ]
                ),
            )

        with pytest.raises(ValueError, match="unknown"):
            harness.job.execute()

        harness.modeler.save.assert_not_called()
        harness.publications.write.assert_not_called()

    def test_duplicate_group_membership_is_rejected(self, corpus: Mock) -> None:
        harness = TrainingHarness(TopicTrainingOptions())
        harness.groups[0].topic_ids.append(0)

        with pytest.raises(ValueError, match="exactly one metasubject"):
            harness.job.execute()

        harness.modeler.save.assert_not_called()
        harness.publications.write.assert_not_called()

    def test_missing_grouped_assignments_are_rejected(self, corpus: Mock) -> None:
        harness = TrainingHarness(TopicTrainingOptions())
        harness.assigner.assign.return_value = []

        with pytest.raises(ValueError, match="exactly one assignment"):
            harness.job.execute()

        harness.modeler.save.assert_not_called()
        harness.publications.write.assert_not_called()

    def test_undated_corpus_has_no_trends(self, tmp_path: Path, corpus: Mock) -> None:
        corpus.return_value[0]["_source"].pop("introduced_date")
        harness = TrainingHarness(TopicTrainingOptions(model_dir=tmp_path))

        run = harness.job.execute()

        assert run is not None
        assert run.dated_documents == run.counts.over_time == 0
        assert run.counts.metasubject_over_time == 0
        harness.modeler.topics_over_time.assert_not_called()

    def test_failed_write_does_not_publish_or_report_success(
        self, tmp_path: Path, corpus: Mock
    ) -> None:
        harness = TrainingHarness(TopicTrainingOptions(model_dir=tmp_path))
        harness.publications.write.side_effect = RuntimeError("partial bulk")

        with pytest.raises(RuntimeError, match="partial bulk"):
            harness.job.execute()

        harness.publications.publish.assert_not_called()
        assert all(progress.progress != 1.0 for progress in harness.progress)

    def test_existing_model_artifacts_survive_publication(
        self, tmp_path: Path, corpus: Mock
    ) -> None:
        retained = tmp_path / "old-model"
        retained.mkdir()
        artifact = retained / "model.safetensors"
        artifact.write_bytes(b"retained model")
        harness = TrainingHarness(TopicTrainingOptions(model_dir=tmp_path))

        assert harness.job.execute() is not None

        assert artifact.read_bytes() == b"retained model"
        harness.client.delete_by_query.assert_not_called()
