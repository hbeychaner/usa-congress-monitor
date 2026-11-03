from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.exc import CompileError

from cdm.jobs.store import (
    _INGEST_WINDOWS,
    _JOBS,
    JobKind,
    JobRow,
    JobStatus,
    JobStore,
)


class LifecycleAction(StrEnum):
    SUCCEED = "succeed"
    FAIL = "fail"
    CANCEL = "cancel"
    RETRY = "retry"
    REQUEUE = "requeue"


class TransitionCase(BaseModel):
    action: LifecycleAction
    target: JobStatus
    sources: frozenset[JobStatus]
    writes_error: bool = False
    finishes: bool = False


@pytest.mark.parametrize("source", list(JobStatus))
@pytest.mark.parametrize(
    "case",
    [
        TransitionCase(
            action=LifecycleAction.SUCCEED,
            target=JobStatus.SUCCEEDED,
            sources=frozenset({JobStatus.RUNNING}),
            finishes=True,
        ),
        TransitionCase(
            action=LifecycleAction.FAIL,
            target=JobStatus.FAILED,
            sources=frozenset({JobStatus.RUNNING, JobStatus.RETRYING}),
            writes_error=True,
            finishes=True,
        ),
        TransitionCase(
            action=LifecycleAction.CANCEL,
            target=JobStatus.CANCELLED,
            sources=frozenset(
                {
                    JobStatus.QUEUED,
                    JobStatus.RUNNING,
                    JobStatus.RETRYING,
                    JobStatus.FAILED,
                }
            ),
            writes_error=True,
            finishes=True,
        ),
        TransitionCase(
            action=LifecycleAction.RETRY,
            target=JobStatus.RETRYING,
            sources=frozenset(set(JobStatus) - {JobStatus.CANCELLED}),
            writes_error=True,
        ),
        TransitionCase(
            action=LifecycleAction.REQUEUE,
            target=JobStatus.QUEUED,
            sources=frozenset(
                {
                    JobStatus.QUEUED,
                    JobStatus.RUNNING,
                    JobStatus.RETRYING,
                    JobStatus.FAILED,
                }
            ),
        ),
    ],
)
def test_existing_transition_guards_and_window_semantics_are_preserved(
    tmp_path: Path, source: JobStatus, case: TransitionCase
) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
    job = store.create(JobKind.INGEST, "transition", {"resources": ["bill"]})
    marker = "2001-01-01T00:00:00+00:00"
    try:
        with store.engine.begin() as connection:
            connection.execute(
                update(_JOBS).values(
                    status=source,
                    last_error="prior",
                    updated_at=marker,
                    finished_at=marker,
                )
            )
            connection.execute(
                update(_INGEST_WINDOWS).values(
                    status=source,
                    last_error="prior",
                    last_progress_at=marker,
                    completed_at=marker,
                )
            )
        before = store.get(job["id"])
        other = store.create(JobKind.INGEST, "unrelated", {"resources": ["member"]})
        other_window = next(
            row for row in store.coverage() if row["job_id"] == other["id"]
        )
        actions: dict[LifecycleAction, Callable[[], JobRow]] = {
            LifecycleAction.SUCCEED: lambda: store.mark_succeeded(job["id"]),
            LifecycleAction.FAIL: lambda: store.mark_failed(job["id"], "event"),
            LifecycleAction.CANCEL: lambda: store.cancel(job["id"], "event"),
            LifecycleAction.RETRY: lambda: store.mark_retrying(job["id"], "event"),
            LifecycleAction.REQUEUE: lambda: store.requeue(job["id"]),
        }

        result = actions[case.action]()

        assert store.get(other["id"]) == other
        assert (
            next(row for row in store.coverage() if row["job_id"] == other["id"])
            == other_window
        )
        changed = source in case.sources
        assert result["status"] == (case.target if changed else source)
        assert result["last_error"] == (
            "event" if changed and case.writes_error else "prior"
        )
        assert (result["finished_at"] != marker) == (changed and case.finishes)
        assert (result["updated_at"] != marker) == changed
        if not changed:
            assert result == before
        window_changed = case.action != LifecycleAction.REQUEUE and (
            source != JobStatus.CANCELLED or case.action == LifecycleAction.CANCEL
        )
        window = store.coverage()[0]
        assert window["status"] == (case.target if window_changed else source)
        assert window["last_error"] == (
            "event" if window_changed and case.writes_error else "prior"
        )
        assert (window["last_progress_at"] != marker) == window_changed
        assert (window["completed_at"] != marker) == (
            window_changed and case.action == LifecycleAction.SUCCEED
        )
    finally:
        store.engine.dispose()


def test_window_failure_rolls_back_the_job_update(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite3", repair=False)
    job = store.create(JobKind.INGEST, "atomic", {"resources": ["bill"]})
    try:
        before = store.mark_running(job["id"])
        windows = store.coverage()

        with pytest.raises(CompileError, match="invalid_window_field"):
            store._transition(
                job["id"],
                update(_JOBS).values(status=JobStatus.SUCCEEDED),
                update(_INGEST_WINDOWS).values(invalid_window_field="rejection"),
            )

        assert store.get(job["id"]) == before
        assert store.coverage() == windows
    finally:
        store.engine.dispose()
