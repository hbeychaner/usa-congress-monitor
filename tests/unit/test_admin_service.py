from datetime import UTC, datetime, timedelta

from cdm.backend.services.admin_service import _job_activity


def _timestamp(*, age_seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=age_seconds)).isoformat()


def test_running_job_with_recent_heartbeat_is_continuing():
    assert _job_activity("running", _timestamp(age_seconds=30)) == "continuing"


def test_running_job_with_stale_heartbeat_is_stalled():
    assert _job_activity("running", _timestamp(age_seconds=121)) == "stalled"


def test_queued_and_missing_heartbeat_states_are_explicit():
    assert _job_activity("queued", None) == "queued"
    assert _job_activity("running", None) == "waiting"
    assert _job_activity("succeeded", None) == "idle"
