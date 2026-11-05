import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from elasticsearch import ConflictError, Elasticsearch

from cdm.perspectives.models import TopicPerspectives
from cdm.store.perspective_repository import PerspectiveRepository


@pytest.fixture
def repository() -> Iterator[PerspectiveRepository]:
    url = os.environ.get("GRAPH_PUBLICATION_TEST_URL")
    if not url:
        pytest.skip("Set GRAPH_PUBLICATION_TEST_URL for isolated real-store checks")
    client = Elasticsearch(
        url, api_key=os.environ.get("GRAPH_PUBLICATION_TEST_API_KEY") or None
    )
    index = f"perspective-cas-test-{uuid4().hex}"
    try:
        yield PerspectiveRepository(client, index)
    finally:
        client.indices.delete(index=index, ignore_unavailable=True)
        client.close()


def test_stale_create_update_and_exact_rollback(repository: PerspectiveRepository) -> None:
    absent = repository.snapshot(119)
    first_time = datetime.now(UTC)
    topic = TopicPerspectives(congress=119, topic_id=1, topic_label="Health", bills=40)
    repository.replace(119, "first", first_time, [topic], expected=absent)
    first = repository.snapshot(119)
    repository.replace(119, "second", datetime.now(UTC), [], expected=first)
    for stale in (absent, first):
        with pytest.raises(ConflictError):
            repository.replace(119, "stale", datetime.now(UTC), [], expected=stale)
    assert repository.read(119) == ([], "second")
    repository.replace(
        119, "first", first_time, [topic], expected=repository.snapshot(119)
    )
    assert repository.snapshot(119).publication == first.publication
    assert repository.read(119) == ([topic], "first")
