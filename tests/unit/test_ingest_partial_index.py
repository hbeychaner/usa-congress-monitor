from pathlib import Path
from typing import Any, cast

from cdm.config.app_config import CongressApiConfig, RedisConfig
from cdm.jobs.payloads import IndexPayload, IngestPayload
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
    )


def _session() -> IngestSession:
    unused: Any = None
    session = IngestSession("job", unused, unused, RedisConfig(), unused, unused)
    session.published_counts.update({"bill": 3, "summaries": 2, "member": 0})
    return session


def test_failed_attempt_indexes_what_it_published(tmp_path: Path) -> None:
    submitter = RecordingSubmitter()
    payload = IngestPayload(outdir=str(tmp_path), index=True)

    _runner(submitter)._queue_partial_index_jobs("job", payload, tmp_path, _session(), 4)

    assert [p.resource for p in submitter.payloads] == ["bill"]
    assert submitter.payloads[0].expected_count is None
    assert submitter.payloads[0].source_attempt == 4
    assert "source_attempt" in submitter.payloads[0].to_json()


def test_partial_indexing_respects_index_flag(tmp_path: Path) -> None:
    submitter = RecordingSubmitter()
    payload = IngestPayload(outdir=str(tmp_path), index=False)

    _runner(submitter)._queue_partial_index_jobs("job", payload, tmp_path, _session(), 1)

    assert submitter.payloads == []
