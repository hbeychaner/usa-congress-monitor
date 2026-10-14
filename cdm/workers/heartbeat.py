"""Keeps a running job's ledger row fresh so crash recovery can tell it is alive."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from cdm.jobs.store import JobStore

logger = logging.getLogger(__name__)


class JobHeartbeat:
    """Touches a job's ledger row on a background thread while it runs."""

    def __init__(self, store: JobStore, interval_seconds: float) -> None:
        self._store = store
        self._interval = interval_seconds

    @contextmanager
    def watch(self, job_id: str) -> Iterator[None]:
        stop = threading.Event()
        thread = threading.Thread(
            target=self._beat, args=(job_id, stop), name=f"heartbeat-{job_id}", daemon=True
        )
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join()

    def _beat(self, job_id: str, stop: threading.Event) -> None:
        while not stop.wait(self._interval):
            try:
                self._store.touch(job_id)
            except Exception:  # noqa: BLE001 - a failed beat must not kill the job.
                logger.warning("Heartbeat failed for %s", job_id, exc_info=True)
