import pytest


@pytest.fixture(autouse=True)
def _no_real_sleep_in_unit_tests(monkeypatch):
    """Neutralize the client's real rate-limit sleep (~0.72s/call) in unit tests.

    CDGClient throttles to ~5000 req/hour in production, which is correct
    there but was adding real wall-clock delay to ingest fixture tests that
    fetch many item details (13+s each). Tests that assert on sleep calls
    (e.g. test_client.py) monkeypatch time.sleep themselves afterward, which
    takes precedence over this fixture.
    """
    monkeypatch.setattr("cdm.data_collection.client.time.sleep", lambda _: None)
