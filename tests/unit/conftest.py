import pytest


@pytest.fixture(autouse=True)
def _no_real_sleep_in_unit_tests(monkeypatch):
    """Neutralize the client's real rate-limit throttling in unit tests.

    CDGClient throttles to ~5000 req/hour in production (via an injected or
    default `TokenBucket`), which is correct there but was adding real
    wall-clock delay to ingest fixture tests that fetch many item details
    (13+s each). `TokenBucket.acquire()` busy-waits against the real
    monotonic clock, so patching `time.sleep` alone would not help; instead
    neutralize `acquire()` itself for all instances. Tests that assert on
    sleep calls (e.g. test_client.py, for the unrelated HTTP 429 retry/backoff
    path) monkeypatch `time.sleep` themselves afterward, which takes
    precedence over this fixture.
    """
    monkeypatch.setattr("cdm.utils.rate_limiter.TokenBucket.acquire", lambda self: None)
