from pathlib import Path
from typing import Any, cast

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from cdm.config.app_config import CongressApiConfig, RedisConfig
from cdm.ingest.redis_stream import RedisRecordStream
from cdm.jobs.payloads import IndexPayload, IngestPayload
from cdm.workers.failures import FailureClassifier
from cdm.workers.ingest_runner import IngestJobRunner, IngestSession


class RecordingSubmitter:
    def __init__(self) -> None:
        self.payloads: list[IndexPayload] = []

    def submit(self, kind: str, payload: dict[str, Any]) -> dict[str, str]:
        self.payloads.append(IndexPayload.model_validate(payload))
        return {"id": f"index-{len(self.payloads)}"}


def _runner(submitter: RecordingSubmitter) -> IngestJobRunner:
    unused: Any = None
    return IngestJobRunner(
        unused,
        unused,
        cast(Any, submitter),
        RedisConfig(),
        CongressApiConfig(),
        unused,
        unused,
        unused,
        100,
    )


def _session(flushes: list[tuple[str, int]], flush_every: int = 2) -> IngestSession:
    unused: Any = None

    def on_flush(resource: str, part: int) -> str:
        flushes.append((resource, part))
        return f"index-{len(flushes)}"

    return IngestSession(
        "job", unused, unused, RedisConfig(), unused, unused, None, flush_every, on_flush
    )


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RedisRecordStream, "publish", lambda *args, **kwargs: None)
    monkeypatch.setattr(RedisRecordStream, "__init__", lambda *args, **kwargs: None)


def test_session_flushes_every_n_records_then_the_remainder() -> None:
    flushes: list[tuple[str, int]] = []
    session = _session(flushes)

    for _ in range(5):
        session.publish_record("bill", {})
    assert flushes == [("bill", 1), ("bill", 2)]

    session.flush_all()
    assert flushes == [("bill", 1), ("bill", 2), ("bill", 3)]
    assert session.index_job_ids == ["index-1", "index-2", "index-3"]
    session.flush_all()
    assert len(flushes) == 3


def test_flush_submits_distinct_index_payloads_per_part(tmp_path: Path) -> None:
    submitter = RecordingSubmitter()
    runner = _runner(submitter)
    payload = IngestPayload(outdir=str(tmp_path), index=True)

    for part in (1, 2):
        runner._flush_index("job", payload, tmp_path, "bill", 4, part)

    assert [p.part for p in submitter.payloads] == [1, 2]
    assert all(p.expected_count is None for p in submitter.payloads)
    assert submitter.payloads[0].to_json() != submitter.payloads[1].to_json()


def test_flush_skips_unindexed_resources_and_index_disabled(tmp_path: Path) -> None:
    submitter = RecordingSubmitter()
    runner = _runner(submitter)

    assert runner._flush_index(
        "job", IngestPayload(outdir=str(tmp_path), index=True), tmp_path, "summaries", 1, 1
    ) is None
    assert runner._flush_index(
        "job", IngestPayload(outdir=str(tmp_path), index=False), tmp_path, "bill", 1, 1
    ) is None
    assert submitter.payloads == []


def test_soft_time_limit_retries_instead_of_failing() -> None:
    assert FailureClassifier().is_transient(SoftTimeLimitExceeded())
