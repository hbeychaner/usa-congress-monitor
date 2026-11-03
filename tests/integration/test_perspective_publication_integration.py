import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from elastic_transport import TransportError
from elasticsearch import ApiError, Elasticsearch
from pydantic import ValidationError

from cdm.backend.services.party_service import PartyService
from cdm.config import PerspectiveConfig
from cdm.config.topic_analysis import (
    PerspectiveKind,
    PerspectiveSchema,
    TopicAnalysisSchema,
)
from cdm.perspectives.models import TopicPerspectives
from cdm.store.perspective_repository import PerspectiveRepository
from cdm.store.topic_publication import TopicPublicationStore


@pytest.fixture
def repository() -> Iterator[PerspectiveRepository]:
    url = os.environ.get("PERSPECTIVE_PUBLICATION_TEST_URL")
    if not url:
        pytest.skip("Set PERSPECTIVE_PUBLICATION_TEST_URL to isolated Elasticsearch")
    client = Elasticsearch(url, request_timeout=30, max_retries=0)
    index = f"perspective-publication-test-{uuid4().hex}"
    client.indices.create(
        index=index,
        mappings={
            "properties": TopicAnalysisSchema.properties()
            | PerspectiveSchema.properties()
        },
    )
    try:
        yield PerspectiveRepository(client, index)
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


def topic(topic_id: int = 1, congress: int = 119, bills: int = 1) -> TopicPerspectives:
    return TopicPerspectives(
        congress=congress,
        topic_id=topic_id,
        topic_label=f"Topic {topic_id}",
        bills=bills,
    )


def test_current_congress_can_be_refreshed_repeatedly(
    repository: PerspectiveRepository,
) -> None:
    today = datetime.now(UTC)
    repository.replace(
        119, "source-model", today - timedelta(days=1), [topic(1), topic(2)]
    )
    assert repository.read(119) == ([topic(1), topic(2)], "source-model")

    updated = [topic(2, bills=5), topic(3)]
    assert repository.replace(119, "source-model", today, updated) == 2
    assert repository.read(119) == (updated, "source-model")
    assert repository.client.count(index=repository.index)["count"] == 1
    mapping = repository.client.indices.get_mapping(index=repository.index)
    assert (
        mapping[repository.index]["mappings"]["properties"]["results"]["enabled"]
        is False
    )


def test_current_and_previous_congress_snapshots_are_independent(
    repository: PerspectiveRepository,
) -> None:
    repository.replace(118, "previous-model", datetime.now(UTC), [topic(congress=118)])
    repository.replace(119, "current-model", datetime.now(UTC), [])
    assert repository.read(118) == ([topic(congress=118)], "previous-model")
    assert repository.read(119) == ([], "current-model")
    assert repository.congresses() == [119, 118]
    response = PartyService(
        repository,
        PerspectiveConfig(),
        TopicPublicationStore(repository.client, repository.index),
    ).overview(None)
    assert response.congress == 119
    assert response.model_version == "current-model"
    assert all(party.total_bills == 0 for party in response.parties)


def test_legacy_rows_are_preserved_but_cannot_mix_into_new_snapshot(
    repository: PerspectiveRepository,
) -> None:
    legacy = {
        **topic().model_dump(mode="json"),
        "kind": PerspectiveKind.PARTY_TOPIC,
        "model_version": "legacy-model",
        "built_at": datetime.now(UTC).isoformat(),
    }
    repository.client.index(
        index=repository.index, id="legacy-row", document=legacy, refresh="wait_for"
    )
    assert repository.read(119) == ([topic()], "legacy-model")
    assert repository.congresses() == [119]
    repository.replace(119, "new-model", datetime.now(UTC), [])
    assert repository.read(119) == ([], "new-model")
    assert (
        repository.client.get(index=repository.index, id="legacy-row")["_source"]
        == legacy
    )


def test_invalid_refresh_preserves_current_snapshot(
    repository: PerspectiveRepository,
) -> None:
    repository.replace(119, "validated-model", datetime.now(UTC), [topic()])
    with pytest.raises(ValidationError, match="Congress"):
        repository.replace(119, "invalid", datetime.now(UTC), [topic(congress=118)])
    assert repository.read(119) == ([topic()], "validated-model")


def test_rejected_write_preserves_current_snapshot(
    repository: PerspectiveRepository,
) -> None:
    repository.replace(119, "validated-model", datetime.now(UTC), [topic()])
    repository.client.indices.put_settings(
        index=repository.index, settings={"index.blocks.write": True}
    )
    with pytest.raises(ApiError):
        repository.replace(119, "rejected-model", datetime.now(UTC), [topic(2)])
    assert repository.read(119) == ([topic()], "validated-model")


def test_oversized_refresh_preserves_current_snapshot(
    repository: PerspectiveRepository,
) -> None:
    maximum = os.environ.get("PERSPECTIVE_PUBLICATION_TEST_MAX_BYTES")
    if not maximum:
        pytest.skip(
            "Set PERSPECTIVE_PUBLICATION_TEST_MAX_BYTES to the test node HTTP limit"
        )
    repository.replace(119, "validated-model", datetime.now(UTC), [topic()])
    oversized = topic()
    oversized.topic_label = "x" * (2 * int(maximum))
    assert len(oversized.model_dump_json().encode()) > int(maximum)
    with pytest.raises((ApiError, TransportError)):
        repository.replace(119, "oversized-model", datetime.now(UTC), [oversized])
    assert repository.read(119) == ([topic()], "validated-model")


def test_daily_source_updates_are_untouched_by_snapshot_refresh(
    repository: PerspectiveRepository,
) -> None:
    source_index = f"{repository.index}-source"
    repository.client.indices.create(index=source_index)
    try:
        source = {"source_type": "bill", "congress": 119, "title": "Original"}
        repository.client.index(index=source_index, id="bill", document=source)
        repository.replace(119, "model", datetime.now(UTC), [topic()])
        source["title"] = "Updated after daily ingest"
        repository.client.index(index=source_index, id="bill", document=source)
        repository.replace(119, "model", datetime.now(UTC), [topic(bills=2)])
        assert repository.client.get(index=source_index, id="bill")["_source"] == source
    finally:
        repository.client.indices.delete(index=source_index)
