from datetime import date

import pytest
import requests
from pydantic import TypeAdapter

from cdm.contracts.hydration import FullTextDownloadError
from cdm.workers.failures import FailureClassifier
from cdm.workers.planners import DailyIngestPlanner

CLASSIFIER = FailureClassifier()
_is_transient = CLASSIFIER.is_transient
_is_retryable_error = CLASSIFIER.is_retryable_error


def _http_error(status_code: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    return requests.HTTPError(response=response)


def test_server_and_rate_limit_errors_are_transient():
    assert _is_transient(_http_error(429))
    assert _is_transient(_http_error(500))
    assert _is_transient(_http_error(503))


def test_client_errors_are_terminal():
    assert not _is_transient(_http_error(400))
    assert not _is_transient(ValueError("invalid model"))


def test_network_errors_are_transient():
    assert _is_transient(requests.Timeout("timed out"))
    assert _is_transient(requests.ConnectionError("disconnected"))
    assert _is_transient(RuntimeError("database is locked"))


def test_recovery_only_targets_transient_error_messages():
    assert _is_retryable_error("server error: 500")
    assert _is_retryable_error("server error: 429")
    assert _is_retryable_error("Connection closed by server.")
    assert _is_retryable_error("sqlite3.OperationalError: database is locked")
    assert not _is_retryable_error("invalid model field")


def test_daily_payload_uses_overlapping_incremental_resources() -> None:
    payload = DailyIngestPlanner().payload(date(2025, 6, 15)).to_json()
    resources = TypeAdapter(list[str]).validate_python(
        payload["resources"], strict=True
    )

    assert payload["mode"] == "daily_incremental"
    assert resources == sorted(resources)
    assert "bill" in resources
    assert "amendment" not in resources
    assert payload["from_date"] == "2025-06-13T00:00:00Z"
    assert payload["to_date"] == "2025-06-15T23:59:59Z"
    assert payload["congress"] == 119
    assert payload["item_resources"] == ["bill"]


class TestFullTextFailureClassification:
    @pytest.mark.parametrize(
        ("cause", "expected"),
        [
            (requests.ConnectionError("remote disconnected"), True),
            (requests.ReadTimeout("slow response"), True),
            (_http_error(429), True),
            (_http_error(503), True),
            (_http_error(404), False),
            (_http_error(400), False),
            (ValueError("invalid text"), False),
            (None, False),
        ],
    )
    def test_only_chained_transient_request_errors_retry(
        self, cause: BaseException | None, expected: bool
    ) -> None:
        error = FullTextDownloadError("Download failed")
        error.__cause__ = cause
        assert FailureClassifier().is_transient(error) is expected

    def test_untyped_runtime_wrapper_does_not_gain_network_retry(self) -> None:
        error = RuntimeError("Parsing failure")
        error.__cause__ = requests.ConnectionError("remote disconnected")
        assert not FailureClassifier().is_transient(error)
