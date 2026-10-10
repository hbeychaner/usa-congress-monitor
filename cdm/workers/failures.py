"""Classification of task failures into transient (retry) and permanent."""

from __future__ import annotations

import requests

from cdm.ingest.govinfo import GovInfoDownloadError


class FailureClassifier:
    """Decides which failures heal on their own and are safe to retry.

    Retrying is always safe because indexing is idempotent and unacked stream
    entries are redelivered.
    """

    _TRANSIENT_MARKERS = (
        "database is locked",
        "disk i/o error",
        "version_conflict_engine_exception",
        "authentication",
        "connectionerror",
        "connection timed out",
        "connectiontimeout",
        "too_many_requests",
        "es_rejected_execution",
        "circuit_breaking",
        "cluster_block",
        "no_shard_available",
        "unavailable_shards_exception",
        "still has",
        "transporterror(5",
        "transporterror(429",
    )
    _RETRYABLE_PREFIXES = (
        "server error: 5",
        "server error: 429",
        "HTTP 5",
        "HTTP 429",
    )
    _RETRYABLE_MARKERS = (
        "connectionerror",
        "connection aborted",
        "connection closed by server",
        "database is locked",
        "disk i/o error",
        "timed out",
        # Connection-level throttling by govinfo.gov surfaces as these.
        "max retries exceeded",
        "failed to resolve",
        "sslerror",
        # Resume dedupe banks progress across attempts, so a task that ran out
        # of time budget is worth retrying from its archive.
        "softtimelimitexceeded",
    )

    def is_transient(self, exc: BaseException) -> bool:
        # Download failures wrap the network cause; classify by the cause.
        if isinstance(exc, GovInfoDownloadError) and isinstance(
            exc.__cause__, Exception
        ):
            return self.is_transient(exc.__cause__)
        if isinstance(exc, requests.HTTPError):
            response = exc.response
            return response is not None and (
                response.status_code == 429 or response.status_code >= 500
            )
        message = str(exc).lower()
        if any(marker in message for marker in self._TRANSIENT_MARKERS):
            return True
        return isinstance(exc, (requests.ConnectionError, requests.Timeout))

    def is_retryable_error(self, error: str | None) -> bool:
        if not error:
            return False
        lowered = error.lower()
        return (
            error.startswith(self._RETRYABLE_PREFIXES)
            or any(marker in lowered for marker in self._TRANSIENT_MARKERS)
            or any(marker in lowered for marker in self._RETRYABLE_MARKERS)
        )
