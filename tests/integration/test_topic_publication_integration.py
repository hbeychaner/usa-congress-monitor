import os
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from itertools import islice
from unittest.mock import Mock
from uuid import uuid4

import pytest
from elasticsearch import ConflictError, Elasticsearch
from elasticsearch.helpers import bulk as real_bulk

from cdm.backend.services.subject_service import SubjectService
from cdm.backend.services.topic_service import TopicService
from cdm.config.topic_analysis import TopicKind
from cdm.graph.topics import TopicModelReader
from cdm.store.metasubject_repository import MetasubjectRepository
from cdm.store.topic_publication import (
    TopicPublicationStore,
    TopicRunCounts,
    TopicRunSpecification,
)
from cdm.utils.json_types import JsonObject


def specification(version: str) -> TopicRunSpecification:
    return TopicRunSpecification(
        model_version=version,
        trained_at=datetime.now(UTC),
        embedding_model="configured-model",
        min_congress=113,
        corpus_size=1,
        dated_documents=1,
        model_path=f"test-models/{version}",
        counts=TopicRunCounts(
            topics=1,
            assignments=1,
            over_time=1,
            metasubjects=1,
            metasubject_over_time=1,
        ),
    )


def actions(
    store: TopicPublicationStore, run: TopicRunSpecification
) -> Iterator[JsonObject]:
    for kind in run.counts.by_kind():
        yield {
            "_index": store.index,
            "_id": f"{kind}:{run.model_version}",
            "kind": kind,
            "model_version": run.model_version,
            "trained_at": run.trained_at.isoformat(),
            "topic_id": 0,
            "name": run.model_version,
            "size": 1,
            "doc_id": "bill:118:hr:1",
            "probability": 1.0,
            "metasubject_id": 7,
            "topic_ids": [0],
            "top_words": ["health"],
            "centroid": [1.0, 0.0],
            "frequency": 1,
            "timestamp": "2025-01-01T00:00:00Z",
        }


@pytest.fixture
def store() -> Iterator[TopicPublicationStore]:
    url = os.environ.get("TOPIC_PUBLICATION_TEST_URL")
    if not url:
        pytest.skip(
            "Set TOPIC_PUBLICATION_TEST_URL to an isolated Elasticsearch server"
        )
    client = Elasticsearch(url, request_timeout=30)
    index = f"topic-publication-test-{uuid4().hex}"
    store = TopicPublicationStore(client, index)
    store.ensure_index()
    try:
        yield store
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


def write(store: TopicPublicationStore, version: str) -> None:
    run = specification(version)
    store.write(run, actions(store, run))


class TestAtomicPublication:
    def test_legacy_rows_are_preserved_but_not_automatically_published(
        self, store: TopicPublicationStore
    ) -> None:
        store.client.index(
            index=store.index,
            id="legacy-topic",
            document={
                "kind": TopicKind.TOPIC,
                "model_version": "legacy",
                "trained_at": "2099-01-01T00:00:00Z",
            },
            refresh="wait_for",
        )

        assert TopicModelReader(store.client, store.index).latest_version() is None
        with pytest.raises(ValueError, match="No validated complete topic run"):
            store.publish("legacy", None)
        assert store.client.exists(index=store.index, id="legacy-topic")

    def test_failure_after_a_successful_batch_does_not_change_any_reader(
        self, store: TopicPublicationStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write(store, "previous")
        store.publish("previous", None)

        def interrupted_bulk(
            client: Elasticsearch, items: Iterable[JsonObject], *, raise_on_error: bool
        ) -> tuple[int, list[JsonObject]]:
            written, errors = real_bulk(
                client, islice(items, 1), raise_on_error=raise_on_error
            )
            assert written == 1 and not errors
            raise RuntimeError("interrupted after first successful batch")

        monkeypatch.setattr("cdm.store.topic_publication.bulk", interrupted_bulk)
        with pytest.raises(RuntimeError, match="first successful batch"):
            write(store, "partial")
        store.client.indices.refresh(index=store.index)

        assert (
            store.client.count(
                index=store.index, query={"term": {"model_version": "partial"}}
            )["count"]
            == 1
        )
        assert (
            TopicModelReader(store.client, store.index).latest_version() == "previous"
        )
        assert (
            TopicService(
                store.client, store.index, Mock(spec=SubjectService)
            ).latest_model_version()[0]
            == "previous"
        )
        groups = MetasubjectRepository(store.client, store.index).latest()
        assert len(groups) == 1 and groups[0].name == "previous"
        assert not store.client.exists(index=store.index, id=f"{TopicKind.RUN}:partial")

    def test_concurrent_finish_cannot_overwrite_a_newer_publication_and_rollback_works(
        self, store: TopicPublicationStore
    ) -> None:
        write(store, "original")
        store.publish("original", None)
        baseline = store.snapshot()
        write(store, "winner")
        write(store, "late-finisher")

        store.publish("winner", baseline)
        with pytest.raises(ConflictError):
            store.publish("late-finisher", baseline)

        current = store.current()
        assert current is not None and current.model_version == "winner"
        store.publish("original", store.snapshot())
        current = store.current()
        assert current is not None and current.model_version == "original"
        assert store.client.exists(index=store.index, id=f"{TopicKind.RUN}:winner")

    def test_first_publication_is_also_safe_against_concurrent_completion(
        self, store: TopicPublicationStore
    ) -> None:
        write(store, "first")
        write(store, "second")

        store.publish("first", None)
        with pytest.raises(ConflictError):
            store.publish("second", None)

        current = store.current()
        assert current is not None and current.model_version == "first"

    def test_rollback_rejects_a_version_whose_records_are_missing(
        self, store: TopicPublicationStore
    ) -> None:
        write(store, "old")
        store.publish("old", None)
        baseline = store.snapshot()
        write(store, "current")
        store.publish("current", baseline)
        store.client.delete(
            index=store.index, id=f"{TopicKind.ASSIGNMENT}:old", refresh="wait_for"
        )

        with pytest.raises(ValueError, match="Incomplete topic run"):
            store.publish("old", store.snapshot())

        current = store.current()
        assert current is not None and current.model_version == "current"
