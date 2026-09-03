from datetime import date

import requests

from cdm.workers.tasks import _is_retryable_error, _is_transient, daily_ingest_payload


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


def test_recovery_only_targets_transient_error_messages():
    assert _is_retryable_error("server error: 500")
    assert _is_retryable_error("server error: 429")
    assert not _is_retryable_error("invalid model field")


def test_daily_payload_uses_overlapping_incremental_resources():
    payload = daily_ingest_payload(date(2025, 6, 15))

    assert payload["mode"] == "daily_incremental"
    assert payload["resources"] == sorted(payload["resources"])
    assert "bill" in payload["resources"]
    assert "amendment" not in payload["resources"]
    assert payload["from_date"] == "2025-06-13T00:00:00Z"
    assert payload["to_date"] == "2025-06-15T23:59:59Z"
    assert payload["congress"] == 119
